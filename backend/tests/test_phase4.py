"""
Phase 4 tests — debate loop logic, graph routing, Python executor safety checks.
"""
from __future__ import annotations

import sys
import ast
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, ".")


# ─── Debate routing tests ──────────────────────────────────────────────────────

class TestDebateRouting:
    def _make_state(self, challenges=None, debate_rounds=0, max_rounds=2):
        from orchestrator.state import initial_state
        state = initial_state("AAPL")
        state["debate_rounds"] = debate_rounds
        state["max_debate_rounds"] = max_rounds
        state["challenges"] = challenges or []
        return state

    def test_should_debate_true_when_unresolved(self):
        from orchestrator.graph_v2 import should_debate
        from orchestrator.state import Challenge

        ch = Challenge(to_agent="market_researcher", question="Why?")
        state = self._make_state(challenges=[ch])
        assert should_debate(state) == "debate_responses"

    def test_should_debate_false_when_all_resolved(self):
        from orchestrator.graph_v2 import should_debate
        from orchestrator.state import Challenge

        ch = Challenge(to_agent="market_researcher", question="Why?")
        ch_resolved = Challenge(**{**ch.model_dump(), "resolved": True})
        state = self._make_state(challenges=[ch_resolved])
        assert should_debate(state) == "portfolio_strategist"

    def test_should_debate_false_when_no_challenges(self):
        from orchestrator.graph_v2 import should_debate
        state = self._make_state(challenges=[])
        assert should_debate(state) == "portfolio_strategist"

    def test_debate_or_strategy_max_rounds_reached(self):
        from orchestrator.graph_v2 import debate_or_strategy
        from orchestrator.state import Challenge

        ch = Challenge(to_agent="fundamental_analyst", question="Explain?")
        # debate_rounds (2) >= max_debate_rounds (2)
        state = self._make_state(challenges=[ch], debate_rounds=2, max_rounds=2)
        assert debate_or_strategy(state) == "portfolio_strategist"

    def test_debate_or_strategy_continues_when_unresolved(self):
        from orchestrator.graph_v2 import debate_or_strategy
        from orchestrator.state import Challenge

        ch = Challenge(to_agent="technical_analyst", question="Support?")
        state = self._make_state(challenges=[ch], debate_rounds=1, max_rounds=2)
        assert debate_or_strategy(state) == "risk_assessor"

    def test_debate_or_strategy_done_when_all_resolved(self):
        from orchestrator.graph_v2 import debate_or_strategy
        from orchestrator.state import Challenge

        ch = Challenge(to_agent="market_researcher", question="Why?")
        ch_resolved = Challenge(**{**ch.model_dump(), "resolved": True})
        state = self._make_state(challenges=[ch_resolved], debate_rounds=1, max_rounds=2)
        assert debate_or_strategy(state) == "portfolio_strategist"


# ─── Python executor safety tests ─────────────────────────────────────────────

class TestPythonExecutorSafety:
    def test_safe_code_passes(self):
        from mcp_servers.python_executor import _check_safe

        code = """
import numpy as np
import pandas as pd
x = np.array([1, 2, 3])
print(x.mean())
"""
        is_safe, reason = _check_safe(code)
        assert is_safe is True
        assert reason == ""

    def test_blocks_os_import(self):
        from mcp_servers.python_executor import _check_safe

        is_safe, reason = _check_safe("import os\nos.system('rm -rf /')")
        assert is_safe is False
        assert "os" in reason

    def test_blocks_subprocess_import(self):
        from mcp_servers.python_executor import _check_safe

        is_safe, reason = _check_safe("import subprocess\nsubprocess.run(['ls'])")
        assert is_safe is False

    def test_blocks_open_call(self):
        from mcp_servers.python_executor import _check_safe

        is_safe, reason = _check_safe("f = open('/etc/passwd', 'r')\nprint(f.read())")
        assert is_safe is False
        assert "open" in reason

    def test_blocks_eval_call(self):
        from mcp_servers.python_executor import _check_safe

        is_safe, reason = _check_safe("result = eval('1+1')")
        assert is_safe is False

    def test_blocks_exec_call(self):
        from mcp_servers.python_executor import _check_safe

        is_safe, reason = _check_safe("exec('import os')")
        assert is_safe is False

    def test_syntax_error_detected(self):
        from mcp_servers.python_executor import _check_safe

        is_safe, reason = _check_safe("def broken(:\n  pass")
        assert is_safe is False
        assert "Syntax error" in reason

    def test_validate_code_tool_valid(self):
        from mcp_servers.python_executor import validate_code

        result = validate_code("x = 1 + 2\nprint(x)")
        assert result["is_valid"] is True
        assert result["syntax_ok"] is True
        assert result["is_safe"] is True

    def test_validate_code_tool_unsafe(self):
        from mcp_servers.python_executor import validate_code

        result = validate_code("import os; os.getcwd()")
        assert result["is_valid"] is False
        assert result["is_safe"] is False


# ─── Risk Assessor parsing tests ──────────────────────────────────────────────

class TestRiskAssessorParsing:
    def test_challenge_from_valid_json(self):
        import json

        from orchestrator.state import Challenge

        raw = json.dumps({
            "overall_assessment": "PROCEED_WITH_CAUTION",
            "challenges": [
                {
                    "to_agent": "market_researcher",
                    "severity": "HIGH",
                    "cited_claim": "Revenue will grow 20% YoY",
                    "question": "What evidence supports 20% growth given sector headwinds?",
                    "supporting_evidence": "Sector grew only 8% last year per fundamental report"
                }
            ]
        })
        data = json.loads(raw)
        ch = Challenge(
            to_agent=data["challenges"][0]["to_agent"],
            question=data["challenges"][0]["question"],
            cited_claim=data["challenges"][0]["cited_claim"],
            supporting_evidence=data["challenges"][0]["supporting_evidence"],
        )
        assert ch.to_agent == "market_researcher"
        assert ch.resolved is False
        assert "20%" in ch.cited_claim

    def test_portfolio_recommendation_parsing(self):
        import json

        from orchestrator.state import Catalyst, ScenarioTarget, TradeRecommendation

        raw = json.dumps({
            "action": "BUY",
            "confidence": 0.78,
            "entry_price": 183.50,
            "stop_loss": 170.00,
            "take_profit": 210.00,
            "time_horizon": "1-3 months",
            "reasoning_summary": "Strong fundamental + bullish technical setup.",
            "scenarios": [
                {"label": "bull", "probability": 0.35, "price_target": 215.0, "return_pct": 17.2, "catalyst": "iPhone supercycle"},
                {"label": "base", "probability": 0.50, "price_target": 195.0, "return_pct": 6.3, "catalyst": "Steady services growth"},
                {"label": "bear", "probability": 0.15, "price_target": 162.0, "return_pct": -11.7, "catalyst": "China slowdown"},
            ],
            "catalysts": [
                {"description": "Q1 2025 earnings", "date_estimate": "2025-01-30", "impact": "positive"}
            ],
            "risk_factors": ["China revenue exposure", "AI competition from Google"],
        })
        data = json.loads(raw)
        rec = TradeRecommendation(
            action=data["action"],
            confidence=data["confidence"],
            entry_price=data["entry_price"],
            stop_loss=data["stop_loss"],
            take_profit=data["take_profit"],
            reasoning_summary=data["reasoning_summary"],
            scenarios=[ScenarioTarget(**s) for s in data["scenarios"]],
            catalysts=[Catalyst(**c) for c in data["catalysts"]],
            risk_factors=data["risk_factors"],
        )
        assert rec.action == "BUY"
        assert rec.confidence == 0.78
        assert len(rec.scenarios) == 3
        assert rec.scenarios[0].probability + rec.scenarios[1].probability + rec.scenarios[2].probability == pytest.approx(1.0)
        assert len(rec.catalysts) == 1
        assert rec.stop_loss < rec.entry_price
        assert rec.take_profit > rec.entry_price

    def test_alpha_vantage_rsi_signal(self):
        """Verify RSI signal logic."""
        def rsi_signal(val: float) -> str:
            return "overbought" if val > 70 else "oversold" if val < 30 else "neutral"

        assert rsi_signal(75) == "overbought"
        assert rsi_signal(25) == "oversold"
        assert rsi_signal(50) == "neutral"
        assert rsi_signal(70.1) == "overbought"
        assert rsi_signal(29.9) == "oversold"
