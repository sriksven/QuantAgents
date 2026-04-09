"""
Phase 3 tests — state schema, MCP server tools, and API endpoint.
"""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pydantic import ValidationError


# ─── State schema tests ────────────────────────────────────────────────────────

class TestFinSightState:
    def test_initial_state_defaults(self):
        import sys
        sys.path.insert(0, ".")
        from orchestrator.state import initial_state

        state = initial_state("AAPL")
        assert state["ticker"] == "AAPL"
        assert state["user_id"] == "default"
        assert state["market_report"] is None
        assert state["fundamental_report"] is None
        assert state["challenges"] == []
        assert state["debate_rounds"] == 0
        assert state["max_debate_rounds"] == 2
        assert state["order_placed"] is False
        assert state["current_phase"] == "research"

    def test_ticker_uppercase(self):
        import sys
        sys.path.insert(0, ".")
        from orchestrator.state import initial_state

        state = initial_state("aapl")
        assert state["ticker"] == "AAPL"

    def test_agent_report_confidence_bounds(self):
        import sys
        sys.path.insert(0, ".")
        from orchestrator.state import AgentReport

        report = AgentReport(agent_name="test", content="test content", confidence=0.75)
        assert report.confidence == 0.75

        with pytest.raises(ValidationError):
            AgentReport(agent_name="test", content="test", confidence=1.5)  # > 1.0

        with pytest.raises(ValidationError):
            AgentReport(agent_name="test", content="test", confidence=-0.1)  # < 0.0

    def test_trade_recommendation_actions(self):
        import sys
        sys.path.insert(0, ".")
        from orchestrator.state import TradeRecommendation

        rec = TradeRecommendation(action="BUY", confidence=0.8)
        assert rec.action == "BUY"
        assert rec.confidence == 0.8
        assert rec.scenarios == []

    def test_challenge_has_id(self):
        import sys
        sys.path.insert(0, ".")
        from orchestrator.state import Challenge

        c = Challenge(to_agent="market_researcher", question="Why did you say X?")
        assert c.id is not None
        assert len(c.id) > 0
        assert c.from_agent == "risk_assessor"
        assert c.resolved is False

    def test_backtest_result_defaults(self):
        import sys
        sys.path.insert(0, ".")
        from orchestrator.state import BacktestResult

        bt = BacktestResult()
        assert bt.validated is False
        assert bt.sharpe_ratio is None
        assert bt.total_trades == 0


# ─── Prompt injection tests ────────────────────────────────────────────────────

class TestPromptInjection:
    def test_inject_context_basic(self):
        import sys
        sys.path.insert(0, ".")
        from orchestrator.prompts import inject_context

        template = "Analyze {ticker} for {user}."
        result = inject_context(template, ticker="MSFT", user="dev")
        assert result == "Analyze MSFT for dev."

    def test_inject_missing_key_becomes_empty(self):
        import sys
        sys.path.insert(0, ".")
        from orchestrator.prompts import inject_context

        template = "Hello {name}. Context: {episodic_context}"
        result = inject_context(template, name="World", episodic_context=None)
        assert "World" in result
        assert "{episodic_context}" not in result

    def test_market_researcher_prompt_has_required_sections(self):
        import sys
        sys.path.insert(0, ".")
        from orchestrator.prompts import MARKET_RESEARCHER_SYSTEM, inject_context

        prompt = inject_context(MARKET_RESEARCHER_SYSTEM, ticker="NVDA", episodic_context="")
        for section in ["Sentiment Score", "Key Headlines", "Upcoming Catalysts", "Confidence"]:
            assert section in prompt, f"Expected section: {section}"

    def test_fundamental_analyst_prompt_has_required_sections(self):
        import sys
        sys.path.insert(0, ".")
        from orchestrator.prompts import FUNDAMENTAL_ANALYST_SYSTEM, inject_context

        prompt = inject_context(FUNDAMENTAL_ANALYST_SYSTEM, ticker="TSLA", episodic_context="")
        for section in ["Revenue Analysis", "Valuation Table", "Balance Sheet"]:
            assert section in prompt, f"Expected section: {section}"


# ─── MCP server tools (unit tests, no API calls) ──────────────────────────────

class TestYahooFinanceMCPTools:
    @patch("yfinance.Ticker")
    def test_get_stock_quote_success(self, mock_ticker_cls):
        import sys
        sys.path.insert(0, ".")
        mock_info = {
            "regularMarketPrice": 182.5,
            "longName": "Apple Inc.",
            "marketCap": 2_800_000_000_000,
            "trailingPE": 28.5,
            "regularMarketChange": 1.2,
            "regularMarketChangePercent": 0.66,
        }
        mock_ticker = MagicMock()
        mock_ticker.info = mock_info
        mock_ticker_cls.return_value = mock_ticker

        from mcp_servers.yahoo_finance import get_stock_quote
        result = get_stock_quote("AAPL")
        assert result["ticker"] == "AAPL"
        assert result["price"] == 182.5
        assert result["market_cap"] == 2_800_000_000_000
        assert "error" not in result

    @patch("yfinance.Ticker")
    def test_get_stock_quote_missing_price(self, mock_ticker_cls):
        import sys
        sys.path.insert(0, ".")
        mock_ticker = MagicMock()
        mock_ticker.info = {}  # empty info
        mock_ticker_cls.return_value = mock_ticker

        from mcp_servers.yahoo_finance import get_stock_quote
        result = get_stock_quote("FAKE123")
        assert "error" in result

    @patch("yfinance.Ticker")
    def test_get_key_ratios_returns_expected_keys(self, mock_ticker_cls):
        import sys
        sys.path.insert(0, ".")
        mock_ticker = MagicMock()
        mock_ticker.info = {
            "trailingPE": 25.0,
            "forwardPE": 20.0,
            "profitMargins": 0.25,
            "returnOnEquity": 1.45,
            "debtToEquity": 150.0,
        }
        mock_ticker_cls.return_value = mock_ticker

        from mcp_servers.yahoo_finance import get_key_ratios
        result = get_key_ratios("AAPL")
        assert "pe_trailing" in result
        assert "net_margin" in result
        assert "roe" in result
        assert "error" not in result


class TestTavilyMCPTools:
    @patch.dict("os.environ", {"TAVILY_API_KEY": "test-key"})
    @patch("mcp_servers.tavily_news._get_client")
    def test_search_news_success(self, mock_get_client):
        import sys
        sys.path.insert(0, ".")
        mock_client = MagicMock()
        mock_client.search.return_value = {
            "answer": "Summary of AAPL news",
            "results": [
                {
                    "title": "Apple Reports Record Earnings",
                    "url": "https://reuters.com/apple-earnings",
                    "content": "Apple Inc. reported record quarterly earnings...",
                    "published_date": "2024-01-30",
                    "score": 0.95,
                }
            ],
        }
        mock_get_client.return_value = mock_client

        from mcp_servers.tavily_news import search_news
        result = search_news("AAPL stock earnings")
        assert result["article_count"] == 1
        assert result["articles"][0]["title"] == "Apple Reports Record Earnings"
        assert "error" not in result
