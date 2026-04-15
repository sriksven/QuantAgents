"""
QuantAgents — LangGraph Orchestrator v2 (Phase 4)
Full 8-node graph with 3-agent research fan-out, conditional debate loop,
Portfolio Strategist synthesis, and memory persistence.

Topology:

    START
      │
  load_memory
      │
  ┌───┼───────────────────────┐
  │   │                       │
  market   fundamental   technical
  researcher  analyst    analyst
  │   │                       │
  └───┴───────────┬───────────┘
              risk_assessor
                  │
         ┌────────┴────────┐
     [challenges?]     [no challenges]
         │                  │
    debate_responses        │
         │                  │
         └───────┬──────────┘
          [more rounds?]
         conditional back ─► risk_assessor (max 2 rounds)
                  │ [done]
          portfolio_strategist
                  │
            save_memory
                  │
                END
"""

from __future__ import annotations

import logging
from functools import lru_cache

from langgraph.graph import END, START, StateGraph

from orchestrator.nodes import (
    load_memory,
    run_fundamental_analyst,
    run_market_researcher,
    save_to_memory,
)
from orchestrator.nodes_phase4 import (
    run_debate_responses,
    run_portfolio_strategist,
    run_risk_assessor,
    run_technical_analyst,
)
from orchestrator.state import FinSightState

logger = logging.getLogger(__name__)


# ── Conditional edge functions ────────────────────────────────────────────────


def should_debate(state: FinSightState) -> str:
    """
    Route after risk_assessor:
    - If there are unresolved challenges → 'debate_responses'
    - Otherwise → 'portfolio_strategist'
    """
    challenges = state.get("challenges") or []
    unresolved = [c for c in challenges if not c.resolved]
    return "debate_responses" if unresolved else "portfolio_strategist"


def debate_or_strategy(state: FinSightState) -> str:
    """
    Route after debate_responses:
    - If max rounds not reached AND there are still unresolved challenges → 'risk_assessor' (re-assess)
    - Otherwise → 'portfolio_strategist'
    """
    debate_rounds = state.get("debate_rounds", 0)
    max_rounds = state.get("max_debate_rounds", 2)
    if debate_rounds >= max_rounds:
        return "portfolio_strategist"
    challenges = state.get("challenges") or []
    still_unresolved = [c for c in challenges if not c.resolved]
    return "risk_assessor" if still_unresolved else "portfolio_strategist"


# ── Graph builder ─────────────────────────────────────────────────────────────


def build_graph_v2():
    """
    Build and compile the Phase 4 LangGraph graph.
    """
    graph = StateGraph(FinSightState)

    # ── Register all nodes ────────────────────────────────────────────────────
    graph.add_node("load_memory", load_memory)
    graph.add_node("market_researcher", run_market_researcher)
    graph.add_node("fundamental_analyst", run_fundamental_analyst)
    graph.add_node("technical_analyst", run_technical_analyst)
    graph.add_node("risk_assessor", run_risk_assessor)
    graph.add_node("debate_responses", run_debate_responses)
    graph.add_node("portfolio_strategist", run_portfolio_strategist)
    graph.add_node("save_memory", save_to_memory)

    # ── Edges: START → memory → 3 parallel research agents ───────────────────
    graph.add_edge(START, "load_memory")
    graph.add_edge("load_memory", "market_researcher")
    graph.add_edge("load_memory", "fundamental_analyst")
    graph.add_edge("load_memory", "technical_analyst")

    # ── Fan-in: all 3 agents → risk_assessor ─────────────────────────────────
    graph.add_edge("market_researcher", "risk_assessor")
    graph.add_edge("fundamental_analyst", "risk_assessor")
    graph.add_edge("technical_analyst", "risk_assessor")

    # ── Conditional: debate or skip to strategy ───────────────────────────────
    graph.add_conditional_edges(
        "risk_assessor",
        should_debate,
        {
            "debate_responses": "debate_responses",
            "portfolio_strategist": "portfolio_strategist",
        },
    )

    # ── Conditional: more debate rounds or move on ────────────────────────────
    graph.add_conditional_edges(
        "debate_responses",
        debate_or_strategy,
        {
            "risk_assessor": "risk_assessor",  # re-assess after responses
            "portfolio_strategist": "portfolio_strategist",
        },
    )

    # ── Strategist → memory → END ─────────────────────────────────────────────
    graph.add_edge("portfolio_strategist", "save_memory")
    graph.add_edge("save_memory", END)

    compiled = graph.compile()
    logger.info("LangGraph v2 compiled: 8 nodes, full debate loop enabled")
    return compiled


@lru_cache(maxsize=1)
def get_graph_v2():
    """Cached compiled Phase 4 graph singleton."""
    return build_graph_v2()
