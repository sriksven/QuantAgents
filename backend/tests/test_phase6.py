"""
Phase 6 tests — options strategy selection, Greeks, IV decision matrix, graph v4 routing.
"""
from __future__ import annotations

import sys
import math

import pytest

sys.path.insert(0, ".")


# ─── Black-Scholes Greeks tests ───────────────────────────────────────────────

class TestBlackScholes:
    def test_call_price_itm(self):
        from services.options_strategy import black_scholes_call
        # Deep ITM call: S >> K → price ≈ S - K
        result = black_scholes_call(S=200, K=150, T=0.25, r=0.05, sigma=0.25)
        assert result["price"] > 49.0  # intrinsic value ~50, time value adds to it
        assert 0.9 < result["delta"] <= 1.0

    def test_call_price_atm(self):
        from services.options_strategy import black_scholes_call
        result = black_scholes_call(S=100, K=100, T=0.25, r=0.05, sigma=0.25)
        assert result["price"] > 0
        # ATM delta ≈ 0.5-0.6
        assert 0.45 < result["delta"] < 0.65

    def test_put_price_via_parity(self):
        from services.options_strategy import black_scholes_call, black_scholes_put
        S, K, T, r, sigma = 100, 100, 0.25, 0.05, 0.25
        call = black_scholes_call(S, K, T, r, sigma)
        put = black_scholes_put(S, K, T, r, sigma)
        # Put-call parity: C - P = S - K*e^(-rT)
        parity = call["price"] - put["price"]
        expected = S - K * math.exp(-r * T)
        assert abs(parity - expected) < 0.01

    def test_put_delta_negative(self):
        from services.options_strategy import black_scholes_put
        result = black_scholes_put(S=100, K=100, T=0.25, r=0.05, sigma=0.25)
        # Put delta should be between -1 and 0
        assert -1.0 < result["delta"] < 0

    def test_zero_tte_returns_zero(self):
        from services.options_strategy import black_scholes_call
        result = black_scholes_call(S=100, K=100, T=0, r=0.05, sigma=0.25)
        assert result["price"] == 0.0

    def test_vega_positive(self):
        from services.options_strategy import black_scholes_call
        result = black_scholes_call(S=100, K=100, T=0.25, r=0.05, sigma=0.25)
        assert result["vega"] > 0

    def test_theta_negative(self):
        from services.options_strategy import black_scholes_call
        result = black_scholes_call(S=100, K=100, T=0.25, r=0.05, sigma=0.25)
        assert result["theta"] < 0  # time decay hurts long options


# ─── Options strategy selection tests ────────────────────────────────────────

class TestOptionsStrategySelection:
    def _select(self, direction, iv_rank, price=100.0):
        from services.options_strategy import select_options_strategy
        return select_options_strategy(direction, iv_rank, current_price=price)

    def test_buy_low_iv_gives_long_call(self):
        result = self._select("BUY", iv_rank=15)
        assert result["strategy_name"] == "long_call"
        assert result["iv_environment"] == "low"

    def test_buy_high_iv_gives_bull_put_spread(self):
        result = self._select("BUY", iv_rank=80)
        assert result["strategy_name"] == "bull_put_spread"
        assert result["iv_environment"] == "high"

    def test_buy_moderate_iv_gives_bull_call_spread(self):
        result = self._select("BUY", iv_rank=50)
        assert result["strategy_name"] == "bull_call_spread"
        assert result["iv_environment"] == "moderate"

    def test_sell_low_iv_gives_long_put(self):
        result = self._select("SELL", iv_rank=20)
        assert result["strategy_name"] == "long_put"

    def test_sell_high_iv_gives_bear_call_spread(self):
        result = self._select("SELL", iv_rank=75)
        assert result["strategy_name"] == "bear_call_spread"

    def test_sell_moderate_iv_gives_bear_put_spread(self):
        result = self._select("SELL", iv_rank=45)
        assert result["strategy_name"] == "bear_put_spread"

    def test_hold_high_iv_gives_iron_condor(self):
        result = self._select("HOLD", iv_rank=72)
        assert result["strategy_name"] == "iron_condor"
        # Iron condor has 4 legs
        assert len(result["suggested_legs"]) == 4

    def test_hold_moderate_iv_gives_covered_call(self):
        result = self._select("HOLD", iv_rank=50)
        assert result["strategy_name"] == "covered_call"

    def test_hold_low_iv_gives_no_trade(self):
        result = self._select("HOLD", iv_rank=10)
        assert result["strategy_name"] == "no_options_trade"
        assert result["suggested_legs"] == []

    def test_pricing_applied_to_legs(self):
        """When current_price provided, legs should have estimated_price."""
        result = self._select("BUY", iv_rank=25, price=150.0)
        priced = result.get("priced_legs", [])
        assert len(priced) > 0
        assert all("estimated_price" in leg for leg in priced)
        assert all("delta" in leg for leg in priced)

    def test_bull_put_spread_has_sell_and_buy_leg(self):
        result = self._select("BUY", iv_rank=80, price=200.0)
        assert result["strategy_name"] == "bull_put_spread"
        actions = [leg["action"] for leg in result["suggested_legs"]]
        assert "sell" in actions
        assert "buy" in actions


# ─── Position sizing tests ────────────────────────────────────────────────────

class TestOptionsPositionSizing:
    def test_basic_sizing(self):
        from services.options_strategy import compute_options_position_size
        result = compute_options_position_size(
            strategy_name="bull_call_spread",
            net_debit_per_share=2.50,
            portfolio_value=100_000,
            confidence=0.8,
        )
        assert result["contracts"] >= 0
        assert result["pct_of_portfolio"] <= 3.0

    def test_no_trade_returns_zero(self):
        from services.options_strategy import compute_options_position_size
        result = compute_options_position_size(
            strategy_name="no_options_trade",
            net_debit_per_share=0.0,
            portfolio_value=100_000,
            confidence=0.9,
        )
        assert result["contracts"] == 0
        assert result["total_premium"] == 0.0

    def test_credit_spread_skipped(self):
        """Negative net_debit (credit received) should return 0 contracts."""
        from services.options_strategy import compute_options_position_size
        result = compute_options_position_size(
            strategy_name="bull_put_spread",
            net_debit_per_share=-1.50,
            portfolio_value=100_000,
            confidence=0.85,
        )
        assert result["contracts"] == 0  # negative debit = credit, skip sizing


# ─── Graph v4 routing tests ───────────────────────────────────────────────────

class TestGraphV4Routing:
    def _base_state(self):
        from orchestrator.state import initial_state
        return initial_state("AAPL")

    def _make_rec(self, action="BUY", confidence=0.75):
        from orchestrator.state import TradeRecommendation
        return TradeRecommendation(action=action, confidence=confidence)

    def _make_backtest(self, validated=True):
        from orchestrator.state import BacktestResult
        return BacktestResult(validated=validated)

    def _make_options(self, strategy="bull_put_spread", confidence=0.70, win_rate=0.62):
        from orchestrator.state import OptionsRecommendation
        return OptionsRecommendation(
            strategy_name=strategy,
            direction="BUY",
            iv_rank=75.0,
            iv_environment="high",
            legs=[],
            confidence=confidence,
            backtest_win_rate=win_rate,
        )

    def test_stock_wins_when_validated(self):
        from orchestrator.graph_v4 import select_execution_path
        state = self._base_state()
        state["recommendation"] = self._make_rec("BUY")
        state["backtest_result"] = self._make_backtest(validated=True)
        state["options_recommendation"] = self._make_options()
        assert select_execution_path(state) == "trade_executor"

    def test_options_wins_when_backtest_fails(self):
        from orchestrator.graph_v4 import select_execution_path
        state = self._base_state()
        state["recommendation"] = self._make_rec("BUY")
        state["backtest_result"] = self._make_backtest(validated=False)
        state["options_recommendation"] = self._make_options()
        assert select_execution_path(state) == "options_executor"

    def test_save_when_hold_no_options(self):
        from orchestrator.graph_v4 import select_execution_path
        state = self._base_state()
        state["recommendation"] = self._make_rec("HOLD")
        state["options_recommendation"] = None
        assert select_execution_path(state) == "save_memory"

    def test_options_executed_on_hold_if_compelling(self):
        from orchestrator.graph_v4 import select_execution_path
        state = self._base_state()
        state["recommendation"] = self._make_rec("HOLD")
        state["options_recommendation"] = self._make_options("iron_condor", confidence=0.65, win_rate=0.60)
        assert select_execution_path(state) == "options_executor"

    def test_save_when_no_recommendation(self):
        from orchestrator.graph_v4 import select_execution_path
        state = self._base_state()
        state["recommendation"] = None
        assert select_execution_path(state) == "save_memory"

    def test_save_when_both_fail(self):
        from orchestrator.graph_v4 import select_execution_path
        state = self._base_state()
        state["recommendation"] = self._make_rec("BUY")
        state["backtest_result"] = self._make_backtest(validated=False)
        state["options_recommendation"] = self._make_options(confidence=0.40, win_rate=0.30)
        assert select_execution_path(state) == "save_memory"
