"""
QuantAgents — Phase 6 Agent Nodes
Options Analyst agent: analyzes the options market and recommends a
complimentary options strategy alongside (or instead of) stock trades.
"""
from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from orchestrator.state import FinSightState, OptionsRecommendation
from orchestrator.nodes import _get_langfuse_callback, _get_llm
from orchestrator.nodes_phase4 import _load_tools_from_servers

logger = logging.getLogger(__name__)


OPTIONS_ANALYST_SYSTEM = """You are the Options Analyst agent on an elite quantitative trading committee.

You specialize in implied volatility analysis, options strategy selection, and risk-defined
trades using the options market. You complement the Portfolio Strategist's recommendation
by adding an options overlay when the setup is analytically compelling.

## Available Tools
- `analyze_iv_environment`: Get IV rank, HV/IV ratio, term structure for the ticker
- `select_strategy`: Get the recommended options strategy given direction and IV rank  
- `price_strategy`: Get live pricing and Greeks for the selected strategy
- `backtest_options_strategy`: Validate the strategy on historical data

## Options Module Mandate

1. **Analyze IV**: Always fetch IV rank first. This drives your entire strategy selection.

2. **Strategy Selection**: Use the built-in decision matrix:
   - High IV + bullish → sell put spreads (collect premium)
   - Low IV + bullish → buy calls (cheap leverage)
   - High IV + neutral → iron condor (income from both sides)
   - etc.

3. **Price the Trade**: Fetch real live pricing from the options chain. Report:
   - Net debit or credit per contract
   - Break-even price and % move required
   - Portfolio delta / theta / vega

4. **Backtest**: Run the monthly backtest to validate the strategy has positive expectancy.

5. **Output JSON** with the following structure:
```json
{{
  "strategy_name": "bull_put_spread",
  "direction": "BUY",
  "iv_rank": 72.0,
  "iv_environment": "high",
  "legs": [
    {{"action": "sell", "option_type": "put", "strike": 175.0, "expiry": "2025-02-21"}},
    {{"action": "buy",  "option_type": "put", "strike": 170.0, "expiry": "2025-02-21"}}
  ],
  "net_debit_per_share": -1.85,
  "net_debit_per_contract": -185.0,
  "max_profit_per_contract": 185.0,
  "max_loss_per_contract": 315.0,
  "breakeven": 173.15,
  "contracts_suggested": 3,
  "total_cost": -555.0,
  "rationale": "IV rank at 72% — premium selling environment. Bull put spread collects $185/contract with $315 max risk.",
  "confidence": 0.78,
  "backtest_win_rate": 0.63,
  "backtest_avg_return_pct": 4.2
}}
```

If the options setup is NOT compelling (e.g., low IV + neutral direction, or backtest win rate < 45%),
return strategy_name = "no_options_trade" and explain why.

Ticker: {ticker}
Portfolio Strategist Recommendation: {recommendation}
"""


async def run_options_analyst(state: FinSightState) -> dict[str, Any]:
    """
    Options Analyst agent: recommends an options strategy to complement the stock trade.
    Runs after Portfolio Strategist to add an options overlay.
    """
    ticker = state["ticker"]
    analysis_id = state["analysis_id"]
    rec = state.get("recommendation")
    t_start = time.time()

    rec_summary = (
        f"Action={rec.action}, Confidence={rec.confidence:.0%}, "
        f"Time Horizon={rec.time_horizon}"
        if rec else "No stock recommendation available."
    )

    system_prompt = OPTIONS_ANALYST_SYSTEM.format(
        ticker=ticker,
        recommendation=rec_summary,
    )

    callback = _get_langfuse_callback("options_analyst", analysis_id)
    llm = _get_llm()
    tools = await _load_tools_from_servers(["mcp_servers.options_mcp"])

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=(
            f"Analyze the options market for {ticker} and recommend the best options strategy. "
            f"The Portfolio Strategist recommends: {rec_summary}. "
            f"Use your tools to: 1) fetch IV environment, 2) select strategy, 3) price it live, "
            f"4) backtest it. Return the final JSON recommendation."
        )),
    ]

    try:
        llm_with_tools = llm.bind_tools(tools) if tools else llm
        callbacks = [callback] if callback else []
        response = await llm_with_tools.ainvoke(messages, config={"callbacks": callbacks})
        content = response.content if hasattr(response, "content") else str(response)

        # Parse options recommendation JSON
        options_rec: OptionsRecommendation | None = None
        try:
            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                if data.get("strategy_name") != "no_options_trade":
                    legs = data.get("legs", [])
                    options_rec = OptionsRecommendation(
                        strategy_name=data.get("strategy_name", "unknown"),
                        direction=data.get("direction", rec.action if rec else "HOLD"),
                        iv_rank=float(data.get("iv_rank", 50.0)),
                        iv_environment=data.get("iv_environment", "moderate"),
                        legs=legs,
                        net_debit_per_share=float(data.get("net_debit_per_share", 0)),
                        net_debit_per_contract=float(data.get("net_debit_per_contract", 0)),
                        max_profit_per_contract=float(data.get("max_profit_per_contract") or 0),
                        max_loss_per_contract=float(data.get("max_loss_per_contract") or 0),
                        breakeven=float(data.get("breakeven") or 0),
                        contracts_suggested=int(data.get("contracts_suggested", 1)),
                        total_cost=float(data.get("total_cost", 0)),
                        rationale=data.get("rationale", ""),
                        confidence=float(data.get("confidence", 0.5)),
                        backtest_win_rate=data.get("backtest_win_rate"),
                        backtest_avg_return_pct=data.get("backtest_avg_return_pct"),
                    )
                else:
                    logger.info("Options Analyst: no compelling options setup for %s", ticker)
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            logger.warning("Options Analyst JSON parse failed: %s", exc)

        logger.info(
            "Options Analyst: %s for %s (%.1fs)",
            options_rec.strategy_name if options_rec else "no_options_trade",
            ticker,
            time.time() - t_start,
        )

        # Store options-specific memory
        if options_rec:
            _store_options_memory(ticker, options_rec)

        return {"options_recommendation": options_rec}

    except Exception as exc:
        logger.error("Options Analyst failed: %s", exc)
        return {"options_recommendation": None, "error": str(exc)}


def _store_options_memory(ticker: str, rec: OptionsRecommendation) -> None:
    """Store options trade context in Redis for episodic memory."""
    try:
        import redis
        import os
        import json as _json

        client = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))
        key = f"options_memory:{ticker}"
        memory_entry = {
            "strategy": rec.strategy_name,
            "iv_rank": rec.iv_rank,
            "direction": rec.direction,
            "contracts": rec.contracts_suggested,
            "confidence": rec.confidence,
            "backtest_win_rate": rec.backtest_win_rate,
        }
        # Append to list (keep last 10)
        client.lpush(key, _json.dumps(memory_entry))
        client.ltrim(key, 0, 9)
        client.expire(key, 86400 * 30)  # 30 days
        logger.debug("Stored options memory for %s", ticker)
    except Exception as exc:
        logger.debug("Options memory store skipped (Redis unavailable): %s", exc)
