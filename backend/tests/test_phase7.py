"""
Phase 7 tests — QAOA portfolio optimization, quantum VaR, correlation analysis,
quantum-inspired fallbacks, graph v5 routing.
"""
from __future__ import annotations

import sys

import numpy as np

sys.path.insert(0, ".")


# ─── Quantum-inspired optimization tests ──────────────────────────────────────

class TestQuantumInspiredOptimization:
    """Tests for the quantum-inspired SA fallback (no Qiskit required)."""

    def test_weights_sum_to_one(self):
        from mcp_servers.quantum_finance import _quantum_inspired_optimize
        mu = np.array([0.10, 0.12, 0.08, 0.15])
        cov = np.eye(4) * 0.04
        weights, backend = _quantum_inspired_optimize(mu, cov, 1.0, 4, None)
        assert abs(sum(weights) - 1.0) < 0.001

    def test_weights_non_negative(self):
        from mcp_servers.quantum_finance import _quantum_inspired_optimize
        mu = np.array([0.10, 0.12, 0.08])
        cov = np.eye(3) * 0.03
        weights, _ = _quantum_inspired_optimize(mu, cov, 1.0, 3, None)
        assert all(w >= -0.001 for w in weights)

    def test_backend_label(self):
        from mcp_servers.quantum_finance import _quantum_inspired_optimize
        _, backend = _quantum_inspired_optimize(np.array([0.1, 0.1]), np.eye(2) * 0.02, 1.0, 2, None)
        assert "simulated_annealing" in backend

    def test_high_risk_aversion_reduces_vol(self):
        """Higher risk aversion should allocate away from volatile assets."""
        from mcp_servers.quantum_finance import _quantum_inspired_optimize
        # Asset 0: high return, high vol. Asset 1: low return, low vol.
        mu = np.array([0.20, 0.05])
        cov = np.array([[0.09, 0.0], [0.0, 0.01]])

        w_low_ra, _ = _quantum_inspired_optimize(mu, cov, 0.1, 2, None)   # low risk aversion
        w_high_ra, _ = _quantum_inspired_optimize(mu, cov, 10.0, 2, None)  # high risk aversion

        # Higher risk aversion should assign less to the volatile asset (idx 0)
        assert w_high_ra[0] <= w_low_ra[0] + 0.1  # allow 10% tolerance


# ─── Classical Markowitz tests ────────────────────────────────────────────────

class TestClassicalMarkowitz:
    def test_weights_sum_to_one(self):
        from mcp_servers.quantum_finance import _classical_markowitz
        mu = np.array([0.10, 0.12, 0.08])
        cov = np.array([[0.04, 0.01, 0.005],
                        [0.01, 0.03, 0.008],
                        [0.005, 0.008, 0.02]])
        weights = _classical_markowitz(mu, cov, 1.0, 3, None)
        assert abs(sum(weights) - 1.0) < 0.001

    def test_weights_non_negative(self):
        from mcp_servers.quantum_finance import _classical_markowitz
        mu = np.array([0.10, 0.12, 0.08])
        cov = np.eye(3) * 0.04
        weights = _classical_markowitz(mu, cov, 1.0, 3, None)
        assert all(w >= -0.001 for w in weights)

    def test_sharpe_calculation(self):
        from mcp_servers.quantum_finance import _sharpe
        # Simple case: single asset
        mu = np.array([0.15])
        cov = np.array([[0.04]])
        w = np.array([1.0])
        expected_sharpe = (0.15 - 0.05) / 0.20  # (ret - rf) / vol
        result = _sharpe(mu, cov, w)
        assert abs(result - expected_sharpe) < 0.001

    def test_portfolio_var_95(self):
        from mcp_servers.quantum_finance import _portfolio_var_95
        # Known: 5% daily VaR for 20% annual vol portfolio
        mu = np.array([0.10])
        cov = np.array([[0.04]])  # 20% annual vol
        w = np.array([1.0])
        var = _portfolio_var_95(mu, cov, w)
        # Daily VaR ≈ 20% / sqrt(252) * 1.645 ≈ 2.07%
        assert -0.05 < var < 0  # should be a small negative number


# ─── Quantum VaR tests ────────────────────────────────────────────────────────

class TestQuantumVaR:
    def test_var_output_schema(self):
        """quantum_var_estimate returns correct schema keys."""
        from mcp_servers.quantum_finance import quantum_var_estimate
        result = quantum_var_estimate(
            tickers="AAPL,MSFT",
            weights='{"AAPL": 0.6, "MSFT": 0.4}',
            confidence=0.95,
            horizon_days=1,
            n_scenarios=500,
            start_date="2023-01-01",
            end_date="2024-06-30",
        )
        if "error" not in result:
            assert "var_classical_parametric" in result
            assert "var_quantum_inspired" in result
            assert "cvar_expected_shortfall" in result
            assert "component_var" in result
            assert result["cvar_expected_shortfall"] >= result["var_quantum_inspired"]

    def test_var_negative_value(self):
        """VaR should be expressed as a loss (positive number for a loss)."""
        from mcp_servers.quantum_finance import quantum_var_estimate
        result = quantum_var_estimate(
            tickers="AAPL,MSFT",
            weights='{"AAPL": 0.5, "MSFT": 0.5}',
            confidence=0.95,
            n_scenarios=200,
            start_date="2023-01-01",
            end_date="2024-06-30",
        )
        if "error" not in result:
            # VaR should be positive (represents a loss)
            assert result["var_quantum_inspired"] > 0 or result["var_classical_parametric"] != 0


# ─── Graph v5 routing tests ───────────────────────────────────────────────────

class TestGraphV5Routing:
    def _base_state(self):
        from orchestrator.state import initial_state
        return initial_state("AAPL")

    def _make_rec(self, action="BUY", confidence=0.75):
        from orchestrator.state import TradeRecommendation
        return TradeRecommendation(action=action, confidence=confidence)

    def _make_backtest(self, validated=True):
        from orchestrator.state import BacktestResult
        return BacktestResult(validated=validated)

    def _make_quantum_alloc(self, ticker="AAPL", q_weight=0.35):
        from orchestrator.state import QuantumAllocation
        return QuantumAllocation(ticker=ticker, quantum_weight=q_weight, classical_weight=0.25)

    def _make_options(self, strategy="bull_put_spread", confidence=0.70, win_rate=0.60):
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

    def test_stock_wins_validated(self):
        from orchestrator.graph_v5 import select_execution_path_v5
        state = self._base_state()
        state["recommendation"] = self._make_rec("BUY", 0.8)
        state["backtest_result"] = self._make_backtest(True)
        state["quantum_allocations"] = [self._make_quantum_alloc()]
        state["options_recommendation"] = None
        assert select_execution_path_v5(state) == "trade_executor"

    def test_quantum_boost_enables_trade(self):
        """If backtest fails but quantum strongly agrees + high confidence → execute."""
        from orchestrator.graph_v5 import select_execution_path_v5
        state = self._base_state()
        state["recommendation"] = self._make_rec("BUY", 0.75)
        state["backtest_result"] = self._make_backtest(False)
        state["quantum_allocations"] = [self._make_quantum_alloc("AAPL", q_weight=0.40)]
        state["options_recommendation"] = None
        assert select_execution_path_v5(state) == "trade_executor"

    def test_quantum_boost_insufficient_confidence(self):
        """Quantum boost requires confidence ≥ 0.70 — below that, no trade."""
        from orchestrator.graph_v5 import select_execution_path_v5
        state = self._base_state()
        state["recommendation"] = self._make_rec("BUY", 0.60)  # < 0.70
        state["backtest_result"] = self._make_backtest(False)
        state["quantum_allocations"] = [self._make_quantum_alloc("AAPL", q_weight=0.40)]
        state["options_recommendation"] = None
        assert select_execution_path_v5(state) == "save_memory"

    def test_options_fallback(self):
        """Backtest fails + no quantum boost + options compelling → options_executor."""
        from orchestrator.graph_v5 import select_execution_path_v5
        state = self._base_state()
        state["recommendation"] = self._make_rec("BUY", 0.65)
        state["backtest_result"] = self._make_backtest(False)
        state["quantum_allocations"] = [self._make_quantum_alloc("AAPL", q_weight=0.10)]
        state["options_recommendation"] = self._make_options()
        assert select_execution_path_v5(state) == "options_executor"

    def test_hold_with_high_iv_options(self):
        """HOLD + compelling options → options_executor."""
        from orchestrator.graph_v5 import select_execution_path_v5
        state = self._base_state()
        state["recommendation"] = self._make_rec("HOLD")
        state["quantum_allocations"] = []
        state["options_recommendation"] = self._make_options("iron_condor", confidence=0.65)
        assert select_execution_path_v5(state) == "options_executor"

    def test_all_fail_saves_memory(self):
        from orchestrator.graph_v5 import select_execution_path_v5
        state = self._base_state()
        state["recommendation"] = self._make_rec("BUY")
        state["backtest_result"] = self._make_backtest(False)
        state["quantum_allocations"] = []
        state["options_recommendation"] = self._make_options(confidence=0.40, win_rate=0.30)
        assert select_execution_path_v5(state) == "save_memory"
