"""
QuantAgents — LangGraph Orchestrator v3 (Phase 5)
Extends v2 with Backtest Engine, Trade Executor, and reward scheduler hooks.

Full Phase 5 topology:

    START
      │
  load_memory + load_rl_context
      │
  ┌───┼───────────────────────────┐
  market   fundamental        technical
  researcher  analyst          analyst
      └───────┬───────────────────┘
          risk_assessor
              │
      ┌───────┴──────────┐
  [debate?]         [skip]
  debate_responses      │
      │                 │
      └────────┬─────────┘
       portfolio_strategist
               │
        backtest_engine ── [HOLD override if invalid]
               │
         ┌─────┴──────┐
     [BUY/SELL]    [HOLD]
     trade_executor   │
         │            │
         └──────┬─────┘
           save_memory
               │
             END
"""
from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from langgraph.graph import END, START, StateGraph

from orchestrator.state import FinSightState
from orchestrator.nodes import (
    load_memory,
    run_market_researcher,
    run_fundamental_analyst,
    save_to_memory,
)
from orchestrator.nodes_phase4 import (
    run_technical_analyst,
    run_risk_assessor,
    run_debate_responses,
    run_portfolio_strategist,
)
from orchestrator.nodes_phase5 import run_backtest_engine, run_trade_executor

logger = logging.getLogger(__name__)


# ── Load RL context node ──────────────────────────────────────────────────────

async def load_rl_context(state: FinSightState) -> dict[str, Any]:
    """
    Load RL reward history from the trade journal to inform agent confidence.
    Injects context string into state.
    """
    ticker = state["ticker"]
    try:
        from mcp_servers.trade_journal import get_rl_reward_history
        result = await get_rl_reward_history(ticker, limit=10)
        context = result.get("context", "")
        return {"rl_context": context or None}
    except Exception as exc:
        logger.warning("RL context load failed for %s: %s", ticker, exc)
        return {"rl_context": None}


# ── Conditional edge functions ────────────────────────────────────────────────
# (imported from graph_v2 for debate routing)

def should_debate(state: FinSightState) -> str:
    challenges = state.get("challenges") or []
    return "debate_responses" if any(not c.resolved for c in challenges) else "portfolio_strategist"


def debate_or_strategy(state: FinSightState) -> str:
    if state.get("debate_rounds", 0) >= state.get("max_debate_rounds", 2):
        return "portfolio_strategist"
    return "risk_assessor" if any(not c.resolved for c in (state.get("challenges") or [])) else "portfolio_strategist"


def execute_or_save(state: FinSightState) -> str:
    """
    After backtest_engine: execute the trade or skip to save_memory.
    """
    rec = state.get("recommendation")
    backtest = state.get("backtest_result")

    if not rec or rec.action == "HOLD":
        return "save_memory"
    if backtest and not backtest.validated:
        return "save_memory"
    return "trade_executor"


# ── Graph builder ─────────────────────────────────────────────────────────────

def build_graph_v3():
    """Build and compile the Phase 5 graph."""
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
    graph.add_node("trade_executor", run_trade_executor)
    graph.add_node("save_memory", save_to_memory)

    # ── Entry: parallel memory loads ─────────────────────────────────────────
    graph.add_edge(START, "load_memory")
    graph.add_edge(START, "load_rl_context")

    # ── Research fan-out after memory ─────────────────────────────────────────
    graph.add_edge("load_memory", "market_researcher")
    graph.add_edge("load_memory", "fundamental_analyst")
    graph.add_edge("load_memory", "technical_analyst")
    graph.add_edge("load_rl_context", "market_researcher")

    # ── Fan-in → risk assessor ────────────────────────────────────────────────
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

    # ── Backtest validation ───────────────────────────────────────────────────
    graph.add_edge("portfolio_strategist", "backtest_engine")

    # ── Conditional execution ─────────────────────────────────────────────────
    graph.add_conditional_edges("backtest_engine", execute_or_save, {
        "trade_executor": "trade_executor",
        "save_memory": "save_memory",
    })

    graph.add_edge("trade_executor", "save_memory")
    graph.add_edge("save_memory", END)

    compiled = graph.compile()
    logger.info("LangGraph v3 compiled: 11 nodes, full trading loop with backtest gate")
    return compiled


@lru_cache(maxsize=1)
def get_graph_v3():
    """Cached compiled Phase 5 graph singleton."""
    return build_graph_v3()
