"""
QuantAgents — LangGraph Orchestrator v1
Builds and returns the compiled CompiledStateGraph.
Phase 3: load_memory → market_researcher ‖ fundamental_analyst → save_memory
Phase 4+: additional agents and debate loop will be added here.
"""
from __future__ import annotations

import logging
from functools import lru_cache

from langgraph.graph import END, START, StateGraph

from orchestrator.state import FinSightState
from orchestrator.nodes import (
    load_memory,
    run_fundamental_analyst,
    run_market_researcher,
    save_to_memory,
)

logger = logging.getLogger(__name__)


def build_graph():
    """
    Build and compile the LangGraph analysis graph.

    Phase 3 topology (parallel research):

        START
          │
      load_memory
          │
      ┌───┴───────────────┐
      │                   │
    market_researcher  fundamental_analyst
      │                   │
      └───────┬───────────┘
          save_memory
              │
             END
    """
    graph = StateGraph(FinSightState)

    # ── Register nodes ────────────────────────────────────────────────────────
    graph.add_node("load_memory", load_memory)
    graph.add_node("market_researcher", run_market_researcher)
    graph.add_node("fundamental_analyst", run_fundamental_analyst)
    graph.add_node("save_memory", save_to_memory)

    # ── Edges ─────────────────────────────────────────────────────────────────
    graph.add_edge(START, "load_memory")

    # Fan out: both research agents run in parallel after memory loads
    graph.add_edge("load_memory", "market_researcher")
    graph.add_edge("load_memory", "fundamental_analyst")

    # Fan in: save memory after both agents complete
    graph.add_edge("market_researcher", "save_memory")
    graph.add_edge("fundamental_analyst", "save_memory")

    graph.add_edge("save_memory", END)

    compiled = graph.compile()
    logger.info("LangGraph compiled: %d nodes, Phase 3 topology", len(graph.nodes))
    return compiled


@lru_cache(maxsize=1)
def get_graph():
    """Cached compiled graph singleton."""
    return build_graph()
