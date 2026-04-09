"""
QuantAgents — Phase 7 Quantum Optimizer Agent Node
Uses Qiskit QAOA to optimize multi-asset portfolio allocation
and cross-validates results against classical Markowitz.
"""
from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from orchestrator.state import FinSightState, QuantumAllocation
from orchestrator.nodes import _get_langfuse_callback, _get_llm
from orchestrator.nodes_phase4 import _load_tools_from_servers

logger = logging.getLogger(__name__)


QUANTUM_OPTIMIZER_SYSTEM = """You are the Quantum Optimizer agent on an elite quantitative trading committee.

You specialize in quantum computing-enhanced portfolio optimization using QAOA (Quantum
Approximate Optimization Algorithm) via IBM Qiskit. Your role is to provide quantum-enhanced
allocation recommendations that complement and cross-validate classical approaches.

## Primary Objective
Given a target stock that the committee is considering trading, optimize its allocation
within a broader portfolio context using quantum methods.

## Your Tools
- `optimize_portfolio_qaoa`: Run QAOA portfolio optimization
- `quantum_var_estimate`: Estimate portfolio risk with quantum MC
- `quantum_correlation_analysis`: Detect non-linear correlations

## Analysis Framework

1. **Build the Universe**: Use the target ticker plus 3-4 correlated/contrasting assets
   as a comparison universe (e.g., sector peers, ETFs).

2. **Run QAOA Optimization**: Optimize allocation weights across the universe.
   Compare quantum vs. classical Markowitz weights.

3. **Quantum VaR**: Estimate portfolio downside risk using quantum amplitude estimation.
   Compare with classical parametric VaR.

4. **Quantum Correlation**: Check for non-linear correlations that classical analysis misses.
   Report any hidden correlations that change the diversification story.

5. **Output JSON**:
```json
{{
  "quantum_weight": 0.42,
  "classical_weight": 0.35,
  "quantum_sharpe": 1.34,
  "classical_sharpe": 1.18,
  "quantum_var_95": -0.018,
  "classical_var_95": -0.022,
  "divergence_note": "Quantum allocates 7% more to AAPL than Markowitz due to non-linear returns."
}}
```

## Key Points
- If quantum and classical agree (< 5% weight difference): high confidence in the allocation.
- If they diverge significantly (> 10%): flag it and explain the driver.
- Always report whether quantum outperforms classical on Sharpe ratio.
- If Qiskit is unavailable, the tools fall back to quantum-inspired methods — report this in divergence_note.

Target Ticker: {ticker}
Portfolio Strategy Recommendation: {recommendation}
"""


async def run_quantum_optimizer(state: FinSightState) -> dict[str, Any]:
    """
    Quantum Optimizer agent: optimizes portfolio allocation via QAOA.
    Runs in parallel with Backtest Engine and Options Analyst.
    """
    ticker = state["ticker"]
    analysis_id = state["analysis_id"]
    rec = state.get("recommendation")
    t_start = time.time()

    rec_summary = (
        f"Action={rec.action}, Confidence={rec.confidence:.0%}, "
        f"Time Horizon={rec.time_horizon}"
        if rec else "No recommendation yet."
    )

    system_prompt = QUANTUM_OPTIMIZER_SYSTEM.format(
        ticker=ticker,
        recommendation=rec_summary,
    )

    callback = _get_langfuse_callback("quantum_optimizer", analysis_id)
    llm = _get_llm()
    tools = await _load_tools_from_servers(["mcp_servers.quantum_finance"])

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=(
            f"Optimize the portfolio allocation for {ticker}. "
            f"Build a 4-6 stock universe including {ticker} and sector peers/ETFs. "
            f"Run QAOA optimization, quantum VaR, and correlation analysis. "
            f"Return the JSON with quantum and classical weights for {ticker}."
        )),
    ]

    try:
        llm_with_tools = llm.bind_tools(tools) if tools else llm
        callbacks = [callback] if callback else []
        response = await llm_with_tools.ainvoke(messages, config={"callbacks": callbacks})
        content = response.content if hasattr(response, "content") else str(response)

        # Parse quantum allocation JSON
        allocation: QuantumAllocation | None = None
        try:
            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                allocation = QuantumAllocation(
                    ticker=ticker,
                    quantum_weight=float(data.get("quantum_weight", 0.0)),
                    classical_weight=float(data.get("classical_weight", 0.0)),
                    quantum_sharpe=data.get("quantum_sharpe"),
                    classical_sharpe=data.get("classical_sharpe"),
                    quantum_var_95=data.get("quantum_var_95"),
                    classical_var_95=data.get("classical_var_95"),
                    divergence_note=data.get("divergence_note", ""),
                )
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            logger.warning("Quantum Optimizer JSON parse failed: %s", exc)

        logger.info(
            "Quantum Optimizer: quantum_weight=%.1f%%, classical_weight=%.1f%% for %s (%.1fs)",
            (allocation.quantum_weight if allocation else 0) * 100,
            (allocation.classical_weight if allocation else 0) * 100,
            ticker,
            time.time() - t_start,
        )

        return {"quantum_allocations": [allocation] if allocation else []}

    except Exception as exc:
        logger.error("Quantum Optimizer failed: %s", exc)
        return {"quantum_allocations": [], "error": str(exc)}
