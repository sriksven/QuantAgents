"""
QuantAgents — LangGraph Orchestrator v4 (Phase 6)
Adds the Options Analyst node in parallel with the Backtest Engine,
then selects the best trade (stock vs. options) before execution.

Full Phase 6 topology:

    START
      │
  [load_memory ‖ load_rl_context]
      │
  [market ‖ fundamental ‖ technical]
      │
  risk_assessor → [debate]*
      │
  portfolio_strategist
      │
  [backtest_engine ‖ options_analyst]  ← parallel validation
      │
  trade_selector  ← picks stock or options execution
      │
  [trade_executor or options_executor]
      │
  save_memory → END
"""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from langgraph.graph import END, START, StateGraph

from orchestrator.state import FinSightState
from orchestrator.nodes import load_memory, run_market_researcher, run_fundamental_analyst, save_to_memory
from orchestrator.nodes_phase4 import run_technical_analyst, run_risk_assessor, run_debate_responses, run_portfolio_strategist
from orchestrator.nodes_phase5 import run_backtest_engine, run_trade_executor
from orchestrator.nodes_phase6 import run_options_analyst
from orchestrator.graph_v3 import load_rl_context

logger = logging.getLogger(__name__)


# ── Routing functions (carried over + extended) ───────────────────────────────

def should_debate(state: FinSightState) -> str:
    challenges = state.get("challenges") or []
    return "debate_responses" if any(not c.resolved for c in challenges) else "portfolio_strategist"


def debate_or_strategy(state: FinSightState) -> str:
    if state.get("debate_rounds", 0) >= state.get("max_debate_rounds", 2):
        return "portfolio_strategist"
    return "risk_assessor" if any(not c.resolved for c in (state.get("challenges") or [])) else "portfolio_strategist"


def select_execution_path(state: FinSightState) -> str:
    """
    After backtest + options analysis, decide execution path:
    - 'trade_executor'   → stock order wins (backtest validated, no options or options weaker)
    - 'options_executor' → options wins (options has higher confidence OR stock backtest failed)
    - 'save_memory'      → HOLD / no trade
    """
    rec = state.get("recommendation")
    backtest = state.get("backtest_result")
    options_rec = state.get("options_recommendation")

    if not rec or rec.action == "HOLD":
        # Check if options makes sense on its own (iron condor etc.)
        if options_rec and options_rec.strategy_name != "no_options_trade" and options_rec.confidence >= 0.55:
            return "options_executor"
        return "save_memory"

    stock_validated = backtest and backtest.validated
    options_compelling = (
        options_rec is not None
        and options_rec.strategy_name != "no_options_trade"
        and options_rec.confidence >= 0.60
        and (options_rec.backtest_win_rate or 0) >= 0.45
    )

    # Options wins if backtest failed but options is compelling
    if not stock_validated and options_compelling:
        return "options_executor"
    # Stock wins if validated
    if stock_validated:
        return "trade_executor"
    # Both failed → no trade
    return "save_memory"


# ── Options Executor node ──────────────────────────────────────────────────────

async def run_options_executor(state: FinSightState) -> dict[str, Any]:
    """
    Execute the options trade via Alpaca options orders (paper trading).
    Currently stubs to log the recommendation — Alpaca options API requires
    enabling options trading on the account (Phase 6 note).
    """
    options_rec = state.get("options_recommendation")
    ticker = state["ticker"]
    analysis_id = state["analysis_id"]

    if not options_rec:
        return {"order_placed": False, "order_id": None, "order_details": {"veto_reason": "No options recommendation"}}

    # Log to trade journal (options trade)
    try:
        from mcp_servers.trade_journal import log_trade
        result = await log_trade(
            analysis_id=analysis_id,
            ticker=ticker,
            action=f"OPTIONS:{options_rec.strategy_name.upper()}",
            qty=float(options_rec.contracts_suggested * 100),  # shares equivalent
            price=abs(options_rec.net_debit_per_share),
            strategy=options_rec.strategy_name,
            confidence=options_rec.confidence,
        )
        order_id = result.get("trade_id")
        logger.info(
            "Options Executor: logged %s × %d contracts for %s (journal_id=%s)",
            options_rec.strategy_name, options_rec.contracts_suggested, ticker, order_id,
        )
    except Exception as exc:
        logger.warning("Options Executor journal log failed: %s", exc)
        order_id = None

    # TODO: Phase 6b — place actual multi-leg options order via Alpaca
    # Alpaca requires Options Trading Agreement and account approval.
    # For now, log the recommended trade and mark as paper-logged.
    return {
        "order_placed": True,  # Paper-logged
        "order_id": order_id,
        "order_details": {
            "type": "options",
            "strategy": options_rec.strategy_name,
            "ticker": ticker,
            "legs": options_rec.legs,
            "contracts": options_rec.contracts_suggested,
            "net_debit_per_contract": options_rec.net_debit_per_contract,
            "total_cost": options_rec.total_cost,
            "rationale": options_rec.rationale,
            "note": "Logged to trade journal — live options execution requires Alpaca options agreement",
        },
    }


# ── Graph builder ─────────────────────────────────────────────────────────────

def build_graph_v4():
    """Build and compile the Phase 6 graph."""
    graph = StateGraph(FinSightState)

    # ── Nodes ─────────────────────────────────────────────────────────────────
    graph.add_node("load_memory", load_memory)
    graph.add_node("load_rl_context", load_rl_context)
    graph.add_node("market_researcher", run_market_researcher)
    graph.add_node("fundamental_analyst", run_fundamental_analyst)
    graph.add_node("technical_analyst", run_technical_analyst)
    graph.add_node("risk_assessor", run_risk_assessor)
    graph.add_node("debate_responses", run_debate_responses)
    graph.add_node("portfolio_strategist", run_portfolio_strategist)
    graph.add_node("backtest_engine", run_backtest_engine)
    graph.add_node("options_analyst", run_options_analyst)
    graph.add_node("trade_executor", run_trade_executor)
    graph.add_node("options_executor", run_options_executor)
    graph.add_node("save_memory", save_to_memory)

    # ── Entry ─────────────────────────────────────────────────────────────────
    graph.add_edge(START, "load_memory")
    graph.add_edge(START, "load_rl_context")

    # ── Research fan-out ──────────────────────────────────────────────────────
    graph.add_edge("load_memory", "market_researcher")
    graph.add_edge("load_memory", "fundamental_analyst")
    graph.add_edge("load_memory", "technical_analyst")
    graph.add_edge("load_rl_context", "market_researcher")

    # ── Fan-in → risk_assessor ────────────────────────────────────────────────
    graph.add_edge("market_researcher", "risk_assessor")
    graph.add_edge("fundamental_analyst", "risk_assessor")
    graph.add_edge("technical_analyst", "risk_assessor")

    # ── Conditional debate ────────────────────────────────────────────────────
    graph.add_conditional_edges("risk_assessor", should_debate, {
        "debate_responses": "debate_responses",
        "portfolio_strategist": "portfolio_strategist",
    })
    graph.add_conditional_edges("debate_responses", debate_or_strategy, {
        "risk_assessor": "risk_assessor",
        "portfolio_strategist": "portfolio_strategist",
    })

    # ── Parallel validation: backtest + options ───────────────────────────────
    graph.add_edge("portfolio_strategist", "backtest_engine")
    graph.add_edge("portfolio_strategist", "options_analyst")

    # ── Trade selection ───────────────────────────────────────────────────────
    graph.add_conditional_edges(
        "backtest_engine",
        select_execution_path,
        {
            "trade_executor": "trade_executor",
            "options_executor": "options_executor",
            "save_memory": "save_memory",
        },
    )

    # Options analyst also feeds into selection but via backtest_engine's conditional
    # (both complete before conditional runs due to parallel fan-out)
    graph.add_edge("options_analyst", "backtest_engine")

    # ── Execution → memory → END ──────────────────────────────────────────────
    graph.add_edge("trade_executor", "save_memory")
    graph.add_edge("options_executor", "save_memory")
    graph.add_edge("save_memory", END)

    compiled = graph.compile()
    logger.info("LangGraph v4 compiled: 13 nodes, options module enabled")
    return compiled


@lru_cache(maxsize=1)
def get_graph_v4():
    """Cached compiled Phase 6 graph singleton."""
    return build_graph_v4()
