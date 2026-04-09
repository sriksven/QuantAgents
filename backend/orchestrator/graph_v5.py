"""
QuantAgents — LangGraph Orchestrator v5 (Phase 7)
Adds the Quantum Optimizer in parallel with Options Analyst + Backtest Engine.
Quantum allocation informs the Trade Executor's position sizing.

Full Phase 7 topology:

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
  [backtest_engine ‖ options_analyst ‖ quantum_optimizer]  ← 3-way parallel
      │
  trade_selector
      │
  [trade_executor | options_executor | save_memory]
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
from orchestrator.nodes_phase7 import run_quantum_optimizer
from orchestrator.graph_v4 import (
    should_debate,
    debate_or_strategy,
    run_options_executor,
)
from orchestrator.graph_v3 import load_rl_context

logger = logging.getLogger(__name__)


# ── Execution path selector (v5: quantum-informed) ────────────────────────────

def select_execution_path_v5(state: FinSightState) -> str:
    """
    After triple parallel validation (backtest + options + quantum):
    - 'trade_executor'   → stock trade (backtest validated)
    - 'options_executor' → options trade (backtest failed but options compelling)
    - 'save_memory'      → no trade

    Quantum allocation modifies position sizing but doesn't block execution.
    """
    rec = state.get("recommendation")
    backtest = state.get("backtest_result")
    options_rec = state.get("options_recommendation")
    quantum_allocs = state.get("quantum_allocations") or []

    # Check if quantum optimizer recommends a meaningful allocation
    q_weight = 0.0
    if quantum_allocs:
        ticker_alloc = next((a for a in quantum_allocs if a.ticker == state.get("ticker", "")), None)
        q_weight = ticker_alloc.quantum_weight if ticker_alloc else 0.0

    if not rec or rec.action == "HOLD":
        # Options standalone on HOLD+high-IV
        options_compelling = (
            options_rec is not None
            and options_rec.strategy_name != "no_options_trade"
            and options_rec.confidence >= 0.55
        )
        return "options_executor" if options_compelling else "save_memory"

    stock_validated = backtest and backtest.validated
    options_compelling = (
        options_rec is not None
        and options_rec.strategy_name != "no_options_trade"
        and options_rec.confidence >= 0.60
        and (options_rec.backtest_win_rate or 0) >= 0.45
    )

    # Quantum boost: if quantum strongly agrees (q_weight > 0.30), lower backtest bar
    quantum_boosts = q_weight >= 0.30

    if stock_validated or (quantum_boosts and rec.confidence >= 0.70):
        return "trade_executor"
    if options_compelling:
        return "options_executor"
    return "save_memory"


# ── Graph builder ─────────────────────────────────────────────────────────────

def build_graph_v5():
    """Build and compile the Phase 7 graph."""
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
    graph.add_node("quantum_optimizer", run_quantum_optimizer)
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

    # ── Triple parallel validation ─────────────────────────────────────────────
    graph.add_edge("portfolio_strategist", "backtest_engine")
    graph.add_edge("portfolio_strategist", "options_analyst")
    graph.add_edge("portfolio_strategist", "quantum_optimizer")

    # Options analyst and quantum optimizer sync into backtest before routing
    graph.add_edge("options_analyst", "backtest_engine")
    graph.add_edge("quantum_optimizer", "backtest_engine")

    # ── Conditional execution ─────────────────────────────────────────────────
    graph.add_conditional_edges(
        "backtest_engine",
        select_execution_path_v5,
        {
            "trade_executor": "trade_executor",
            "options_executor": "options_executor",
            "save_memory": "save_memory",
        },
    )

    # ── Finalize ──────────────────────────────────────────────────────────────
    graph.add_edge("trade_executor", "save_memory")
    graph.add_edge("options_executor", "save_memory")
    graph.add_edge("save_memory", END)

    compiled = graph.compile()
    logger.info("LangGraph v5 compiled: 14 nodes, quantum module enabled")
    return compiled


@lru_cache(maxsize=1)
def get_graph_v5():
    """Cached compiled Phase 7 graph singleton."""
    return build_graph_v5()
