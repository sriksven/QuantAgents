"""
QuantAgents — Phase 5 Agent Nodes
Backtest Engine and Trade Executor agents.
"""
from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from orchestrator.state import BacktestResult, FinSightState
from orchestrator.nodes import _get_langfuse_callback, _get_llm
from orchestrator.nodes_phase4 import _load_tools_from_servers
from services.position_sizing import compute_position_size

logger = logging.getLogger(__name__)


BACKTEST_ENGINE_SYSTEM = """You are the Backtest Engine agent on an elite quantitative trading committee.

Your job: given the Portfolio Strategist's recommendation, select the best technical strategy,
run a rigorous backtest, and then run a Monte Carlo simulation to validate robustness.

## Recommendation Under Review
Action: {action}
Confidence: {confidence}
Time Horizon: {time_horizon}
Reasoning: {reasoning}

## Your Mandate

1. **Strategy Selection**: Based on the recommendation, select the most appropriate strategy to backtest:
   - BUY + momentum signals → try macd_momentum or sma_crossover
   - BUY + mean-reversion signals → try rsi_mean_reversion or bollinger_breakout
   - Any → always compare against buy_and_hold as a benchmark

2. **Run Backtest**: Use the `run_backtest` tool for your chosen strategy over a 2-3 year period.

3. **Run Monte Carlo**: Use `run_monte_carlo` to simulate 1000 paths and estimate outcome distribution.

4. **Validate**: Compare the strategy to the buy-and-hold benchmark. If the strategy doesn't beat buy-and-hold
   with a Sharpe ≥ 1.0, recommend reverting to buy-and-hold.

5. **Go/No-Go Decision**: Explicitly state whether the backtest results VALIDATE or INVALIDATE the trade.

## Output

State your decision clearly:
- VALIDATED: Backtest supports the trade. Cite specific metrics.
- INVALIDATED: Backtest does not support the trade. Recommend HOLD instead.
- CONDITIONAL: Strategy is marginal — specify conditions under which to proceed.

Include a comparison table: Strategy vs Buy-and-Hold (Sharpe, Max Drawdown, Total Return, Win Rate).
"""


TRADE_EXECUTOR_SYSTEM = """You are the Trade Executor agent on an elite quantitative trading committee.

Your role: review the validated recommendation, fetch account data, compute position size using the
half-Kelly criterion, and place the order via Alpaca (paper trading).

## Pre-Execution Checklist

Before placing any order, you MUST verify:
1. ✅ Backtest result is VALIDATED (not INVALIDATED)
2. ✅ Account is not trading_blocked
3. ✅ Sufficient buying power for the position
4. ✅ Position size ≤ 5% of portfolio
5. ✅ Not already over-concentrated in this sector
6. ✅ No existing position that makes this trade contradictory

## Your Tools
- `get_account`: Get account equity and buying power
- `get_positions`: Check existing positions
- `get_latest_quote`: Get current price and spread
- `place_market_order`: Place the order (paper trading)
- `log_trade`: Record the trade in the journal

## Output Format

Report:
1. Pre-execution checklist result (all items ✅ or ❌ with reason)
2. Position sizing calculation (show your Kelly math)
3. Order details (if placed): order_id, shares, notional, entry price
4. If NOT placing: explicit reason why the trade was vetoed

Be transparent. If you vetoed the trade, explain which checklist item failed.
"""


# ── Backtest Engine ───────────────────────────────────────────────────────────

async def run_backtest_engine(state: FinSightState) -> dict[str, Any]:
    """
    Run backtests to validate the Portfolio Strategist's recommendation.
    Uses Monte Carlo to estimate outcome distribution.
    """
    ticker = state["ticker"]
    analysis_id = state["analysis_id"]
    rec = state.get("recommendation")
    t_start = time.time()

    if not rec:
        logger.warning("Backtest Engine: no recommendation in state, skipping")
        return {"backtest_result": BacktestResult(
            strategy_description="No recommendation to validate",
            validated=False,
            rejection_reason="Missing recommendation from Portfolio Strategist",
        )}

    system_prompt = BACKTEST_ENGINE_SYSTEM.format(
        action=rec.action,
        confidence=f"{rec.confidence:.0%}",
        time_horizon=rec.time_horizon,
        reasoning=rec.reasoning_summary,
    )

    callback = _get_langfuse_callback("backtest_engine", analysis_id)
    llm = _get_llm()
    tools = await _load_tools_from_servers(["mcp_servers.backtest"])

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=(
            f"Validate the {rec.action} recommendation for {ticker}. "
            f"Run the backtest and Monte Carlo simulation. "
            f"Time horizon: {rec.time_horizon}. "
            f"Provide your VALIDATED/INVALIDATED verdict with supporting metrics."
        )),
    ]

    try:
        llm_with_tools = llm.bind_tools(tools) if tools else llm
        callbacks = [callback] if callback else []
        response = await llm_with_tools.ainvoke(messages, config={"callbacks": callbacks})
        content = response.content if hasattr(response, "content") else str(response)

        # Parse key metrics from LLM response
        validated = "VALIDATED" in content.upper() and "INVALIDATED" not in content.upper()
        rejection_reason = None
        if not validated:
            match = re.search(r"INVALIDATED[:\s]+(.+?)(?:\n|$)", content, re.IGNORECASE)
            rejection_reason = match.group(1).strip()[:300] if match else "Strategy did not meet minimum thresholds"

        # Try to extract numeric metrics from the response
        def extract_float(pattern: str, text: str) -> float | None:
            m = re.search(pattern, text, re.IGNORECASE)
            return float(m.group(1)) if m else None

        backtest_result = BacktestResult(
            strategy_description=content[:600],
            validated=validated,
            rejection_reason=rejection_reason,
            sharpe_ratio=extract_float(r"sharpe[:\s]+([\d.]+)", content),
            max_drawdown_pct=extract_float(r"max.drawdown[:\s]+([\-\d.]+)%?", content),
            win_rate=extract_float(r"win.rate[:\s]+([\d.]+)%?", content),
            total_trades=int(extract_float(r"total.trades[:\s]+(\d+)", content) or 0),
            profit_factor=extract_float(r"profit.factor[:\s]+([\d.]+)", content),
        )

        if not validated and rec:
            # Override recommendation to HOLD if backtest fails
            from orchestrator.state import TradeRecommendation
            updated_rec = TradeRecommendation(
                action="HOLD",
                confidence=rec.confidence,
                reasoning_summary=f"Overridden to HOLD: backtest validation failed. {rejection_reason}",
            )
            logger.warning("Backtest Engine INVALIDATED trade — overriding to HOLD")
            return {"backtest_result": backtest_result, "recommendation": updated_rec}

        logger.info("Backtest Engine: %s in %.1fs", "VALIDATED" if validated else "INVALIDATED", time.time() - t_start)
        return {"backtest_result": backtest_result}

    except Exception as exc:
        logger.error("Backtest Engine failed: %s", exc)
        return {
            "backtest_result": BacktestResult(
                strategy_description=f"Agent error: {exc}",
                validated=False,
                rejection_reason=str(exc),
            ),
            "error": str(exc),
        }


# ── Trade Executor ────────────────────────────────────────────────────────────

async def run_trade_executor(state: FinSightState) -> dict[str, Any]:
    """
    Execute the validated trade via Alpaca with position sizing.
    Runs pre-execution safety checklist.
    """
    ticker = state["ticker"]
    analysis_id = state["analysis_id"]
    rec = state.get("recommendation")
    backtest = state.get("backtest_result")
    t_start = time.time()

    # Gate 1: Backtest must be validated
    if backtest and not backtest.validated:
        logger.info("Trade Executor: vetoed (backtest not validated)")
        return {
            "order_placed": False,
            "order_id": None,
            "order_details": {"veto_reason": "Backtest validation failed"},
        }

    # Gate 2: Must be a BUY or SELL (not HOLD)
    if not rec or rec.action == "HOLD":
        logger.info("Trade Executor: no order — recommendation is HOLD")
        return {"order_placed": False, "order_id": None, "order_details": {"veto_reason": "HOLD recommendation"}}

    callback = _get_langfuse_callback("trade_executor", analysis_id)
    llm = _get_llm()
    tools = await _load_tools_from_servers([
        "mcp_servers.alpaca_trading",
        "mcp_servers.trade_journal",
    ])

    # Fetch position sizing data inline (to not rely on LLM for math)
    try:
        from mcp_servers.alpaca_trading import get_account, get_latest_quote, get_positions
        account_data = get_account()
        quote_data = get_latest_quote(ticker)
        position_data = get_positions()

        portfolio_value = account_data.get("portfolio_value", 0) or 100_000
        current_price = quote_data.get("mid") or quote_data.get("ask") or 0
        buying_power = account_data.get("buying_power", 0) or 0
        trading_blocked = account_data.get("trading_blocked", False)

        existing_pos_value = 0.0
        for pos in (position_data.get("positions") or []):
            if pos.get("symbol") == ticker.upper():
                existing_pos_value = float(pos.get("market_value") or 0)

        win_rate = 0.55  # default; would be loaded from trade journal in full impl
        if backtest and backtest.win_rate:
            win_rate = backtest.win_rate

    except Exception as exc:
        logger.warning("Trade Executor: could not fetch live data: %s — using defaults", exc)
        portfolio_value = 100_000
        current_price = rec.entry_price or 100
        buying_power = 50_000
        trading_blocked = False
        existing_pos_value = 0.0
        win_rate = 0.55

    # Compute position size
    sizing = compute_position_size(
        ticker=ticker,
        action=rec.action,
        recommendation_confidence=rec.confidence,
        portfolio_value=portfolio_value,
        current_price=current_price,
        win_rate=win_rate,
        existing_position_value=existing_pos_value,
    )

    # Gate 3: Safety checks
    if trading_blocked:
        return {"order_placed": False, "order_id": None, "order_details": {"veto_reason": "Account is trading_blocked"}}
    if sizing["recommended_shares"] <= 0:
        return {"order_placed": False, "order_id": None, "order_details": {"veto_reason": "Position sizing returned 0 shares", "sizing": sizing}}
    if sizing["notional"] > buying_power:
        return {"order_placed": False, "order_id": None, "order_details": {
            "veto_reason": f"Insufficient buying power: need ${sizing['notional']:,.0f}, have ${buying_power:,.0f}"
        }}

    # Use LLM to execute the order via MCP tools
    system_prompt = TRADE_EXECUTOR_SYSTEM
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=(
            f"Execute this validated {rec.action} for {ticker}:\n"
            f"- Shares: {sizing['recommended_shares']} (${sizing['notional']:,.2f} notional)\n"
            f"- Current price: ${current_price:.2f}\n"
            f"- Stop loss: ${sizing['stop_loss_price']:.2f}\n"
            f"- Position sizing: {sizing['reasoning']}\n\n"
            f"Pre-execution checklist already passed (trading_blocked=False, buying_power sufficient).\n"
            f"Place the market order, then log the trade to the journal with analysis_id={analysis_id}."
        )),
    ]

    try:
        llm_with_tools = llm.bind_tools(tools) if tools else llm
        callbacks = [callback] if callback else []
        response = await llm_with_tools.ainvoke(messages, config={"callbacks": callbacks})
        content = response.content if hasattr(response, "content") else str(response)

        # Try to extract order_id from the response
        order_id = None
        order_id_match = re.search(r"order.id[\":\s]+([0-9a-f\-]{36})", content, re.IGNORECASE)
        if order_id_match:
            order_id = order_id_match.group(1)

        order_placed = bool(order_id or ("submitted" in content.lower() or "placed" in content.lower()))

        logger.info(
            "Trade Executor: order_placed=%s, order_id=%s, ticker=%s, action=%s, shares=%d (%.1fs)",
            order_placed, order_id, ticker, rec.action, sizing["recommended_shares"], time.time() - t_start,
        )

        return {
            "order_placed": order_placed,
            "order_id": order_id,
            "order_details": {
                "ticker": ticker,
                "action": rec.action,
                "shares": sizing["recommended_shares"],
                "notional": sizing["notional"],
                "entry_price": current_price,
                "stop_loss": sizing["stop_loss_price"],
                "take_profit": sizing["take_profit_price"],
                "pct_of_portfolio": sizing["pct_of_portfolio"],
                "execution_notes": content[:400],
            },
        }
    except Exception as exc:
        logger.error("Trade Executor failed during execution: %s", exc)
        return {"order_placed": False, "order_id": None, "order_details": {"error": str(exc)}}
