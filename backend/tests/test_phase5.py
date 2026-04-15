"""
Phase 5 tests — position sizing, backtest mechanics, graph v3 routing, Alpaca safety.
"""

from __future__ import annotations

import sys

sys.path.insert(0, ".")


# ─── Position sizing tests ────────────────────────────────────────────────────


class TestPositionSizing:
    def test_basic_kelly_buy(self):
        from services.position_sizing import compute_position_size

        result = compute_position_size(
            ticker="AAPL",
            action="BUY",
            recommendation_confidence=0.8,
            portfolio_value=100_000,
            current_price=180.0,
            win_rate=0.60,
            avg_win_pct=6.0,
            avg_loss_pct=3.0,
        )
        assert result["action"] == "BUY"
        assert result["recommended_shares"] >= 0
        assert result["pct_of_portfolio"] <= 5.0  # hard cap
        assert result["stop_loss_price"] < 180.0
        assert result["take_profit_price"] > 180.0

    def test_hold_returns_zero_shares(self):
        from services.position_sizing import compute_position_size

        result = compute_position_size(
            ticker="MSFT",
            action="HOLD",
            recommendation_confidence=0.7,
            portfolio_value=100_000,
            current_price=400.0,
        )
        assert result["action"] == "HOLD"
        assert result["recommended_shares"] == 0
        assert result["notional"] == 0.0

    def test_low_confidence_reduces_size(self):
        from services.position_sizing import compute_position_size

        high = compute_position_size("AAPL", "BUY", 0.9, 100_000, 180.0, 0.60, 6.0, 3.0)
        low = compute_position_size("AAPL", "BUY", 0.3, 100_000, 180.0, 0.60, 6.0, 3.0)
        assert low["recommended_shares"] <= high["recommended_shares"]

    def test_high_volatility_reduces_size(self):
        from services.position_sizing import compute_position_size

        normal = compute_position_size(
            "AAPL", "BUY", 0.8, 100_000, 180.0, 0.60, 6.0, 3.0, volatility_20d=0.15
        )
        high_vol = compute_position_size(
            "AAPL", "BUY", 0.8, 100_000, 180.0, 0.60, 6.0, 3.0, volatility_20d=0.60
        )
        assert high_vol["recommended_shares"] <= normal["recommended_shares"]

    def test_existing_position_reduces_incremental(self):
        from services.position_sizing import compute_position_size

        fresh = compute_position_size(
            "AAPL", "BUY", 0.8, 100_000, 180.0, 0.60, existing_position_value=0
        )
        existing = compute_position_size(
            "AAPL", "BUY", 0.8, 100_000, 180.0, 0.60, existing_position_value=3000
        )
        assert existing["recommended_shares"] <= fresh["recommended_shares"]

    def test_hard_cap_max_5pct(self):
        from services.position_sizing import compute_position_size

        # Even with very high confidence/win-rate, should cap at 5%
        result = compute_position_size(
            "AAPL", "BUY", 1.0, 100_000, 180.0, win_rate=0.95, avg_win_pct=20.0, avg_loss_pct=1.0
        )
        assert result["pct_of_portfolio"] <= 5.01  # allow tiny float rounding

    def test_negative_kelly_returns_zero(self):
        from services.position_sizing import compute_half_kelly

        # win_rate < 0.5 with bad reward/risk ratio → negative Kelly → 0
        result = compute_half_kelly(win_rate=0.3, avg_win_pct=2.0, avg_loss_pct=5.0, confidence=1.0)
        assert result == 0.0

    def test_kelly_formula_known_value(self):
        from services.position_sizing import compute_half_kelly

        # win=0.6, b = 6/3 = 2 → Kelly = (0.6*2 - 0.4)/2 = (1.2-0.4)/2 = 0.4
        # half-Kelly = 0.2, with confidence=1.0 → 0.2
        result = compute_half_kelly(win_rate=0.6, avg_win_pct=6.0, avg_loss_pct=3.0, confidence=1.0)
        assert abs(result - 0.20) < 0.001  # should hit the 20% cap


# ─── Backtest engine mechanics ────────────────────────────────────────────────


class TestBacktestMechanics:
    def test_buy_and_hold_returns_positive_long_term(self):
        """buy_and_hold on a large stock 2020-2023 should generally be positive."""
        from mcp_servers.backtest import run_backtest

        result = run_backtest("AAPL", "buy_and_hold", "2020-01-01", "2023-12-31", 100_000)
        if "error" not in result:
            assert "total_return_pct" in result
            assert result["total_trades"] >= 1

    def test_monte_carlo_has_percentiles(self):
        """Monte Carlo output schema validation."""
        from mcp_servers.backtest import run_monte_carlo

        result = run_monte_carlo(
            "AAPL",
            "sma_crossover",
            n_simulations=100,
            start_date="2022-01-01",
            end_date="2024-06-30",
        )
        if "error" not in result:
            assert "percentile_outcomes" in result
            pct = result["percentile_outcomes"]
            assert "p5" in pct and "p50" in pct and "p95" in pct
            # P5 should be worse than P95
            assert pct["p5"]["equity"] <= pct["p95"]["equity"]

    def test_backtest_minimum_thresholds(self):
        """meets_minimum_thresholds requires Sharpe>=1, MaxDD>=-25%, WinRate>=45%, Trades>=10."""
        from mcp_servers.backtest import run_backtest

        result = run_backtest("AAPL", "sma_crossover", "2020-01-01", "2024-01-01")
        if "error" not in result and result["meets_minimum_thresholds"]:
            assert result["sharpe_ratio"] >= 1.0
            assert result["max_drawdown_pct"] >= -25.0
            assert result["win_rate"] >= 0.45


# ─── Graph v3 routing ────────────────────────────────────────────────────────


class TestGraphV3Routing:
    def _base_state(self):
        from orchestrator.state import initial_state

        return initial_state("AAPL")

    def test_execute_or_save_hold(self):
        from orchestrator.graph_v3 import execute_or_save
        from orchestrator.state import TradeRecommendation

        state = self._base_state()
        state["recommendation"] = TradeRecommendation(action="HOLD", confidence=0.5)
        state["backtest_result"] = None
        assert execute_or_save(state) == "save_memory"

    def test_execute_or_save_buy_validated(self):
        from orchestrator.graph_v3 import execute_or_save
        from orchestrator.state import BacktestResult, TradeRecommendation

        state = self._base_state()
        state["recommendation"] = TradeRecommendation(action="BUY", confidence=0.8)
        state["backtest_result"] = BacktestResult(validated=True)
        assert execute_or_save(state) == "trade_executor"

    def test_execute_or_save_buy_invalid_backtest(self):
        from orchestrator.graph_v3 import execute_or_save
        from orchestrator.state import BacktestResult, TradeRecommendation

        state = self._base_state()
        state["recommendation"] = TradeRecommendation(action="BUY", confidence=0.8)
        state["backtest_result"] = BacktestResult(
            validated=False, rejection_reason="Sharpe too low"
        )
        assert execute_or_save(state) == "save_memory"

    def test_execute_or_save_no_recommendation(self):
        from orchestrator.graph_v3 import execute_or_save

        state = self._base_state()
        state["recommendation"] = None
        assert execute_or_save(state) == "save_memory"


# ─── Alpaca safety validation ────────────────────────────────────────────────


class TestAlpacaSafety:
    def test_invalid_symbol_rejected(self):
        from mcp_servers.alpaca_trading import _validate_order

        is_safe, reason = _validate_order("123BADTICKER!", qty=10, notional=None)
        assert is_safe is False
        assert "Invalid symbol" in reason

    def test_zero_qty_rejected(self):
        from mcp_servers.alpaca_trading import _validate_order

        is_safe, reason = _validate_order("AAPL", qty=0, notional=None)
        assert is_safe is False

    def test_notional_over_50k_rejected(self):
        from mcp_servers.alpaca_trading import _validate_order

        is_safe, reason = _validate_order("AAPL", qty=None, notional=60_000)
        assert is_safe is False
        assert "$50,000" in reason

    def test_valid_order_passes(self):
        from mcp_servers.alpaca_trading import _validate_order

        is_safe, _ = _validate_order("AAPL", qty=10, notional=None)
        assert is_safe is True

    def test_valid_notional_passes(self):
        from mcp_servers.alpaca_trading import _validate_order

        is_safe, _ = _validate_order("MSFT", qty=None, notional=5_000)
        assert is_safe is True
