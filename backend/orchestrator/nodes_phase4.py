"""
QuantAgents — Phase 4 Agent Nodes
Technical Analyst, Risk Assessor (with debate loop), Portfolio Strategist.
Extends orchestrator/nodes.py from Phase 3.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage

from orchestrator.nodes import _get_langfuse_callback, _get_llm, _save_episodic_memory
from orchestrator.prompts import (
    PORTFOLIO_STRATEGIST_SYSTEM,
    RISK_ASSESSOR_SYSTEM,
    TECHNICAL_ANALYST_SYSTEM,
    inject_context,
)
from orchestrator.state import (
    AgentReport,
    Catalyst,
    Challenge,
    FinSightState,
    ScenarioTarget,
    TradeRecommendation,
)

logger = logging.getLogger(__name__)


# ── Helper: load MCP tools (graceful fallback) ────────────────────────────────


async def _load_tools_from_servers(servers: list[str]) -> list:
    """
    Try to load tools from multiple MCP stdio servers.
    Returns empty list if MCP unavailable (graceful fallback).
    """
    from langchain_mcp_adapters.tools import load_mcp_tools
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    tools = []
    for module in servers:
        params = StdioServerParameters(command="python", args=["-m", module])
        try:
            async with stdio_client(params) as (read, write), ClientSession(read, write) as session:
                await session.initialize()
                tools.extend(await load_mcp_tools(session))
        except Exception as exc:
            logger.warning("Could not load MCP tools from %s: %s", module, exc)
    return tools


def _extract_confidence(content: str, default: float = 0.65) -> float:
    match = re.search(r"(?:confidence|rating)[:\s]+(\d+)%", content, re.IGNORECASE)
    if match:
        return min(float(match.group(1)) / 100, 1.0)
    return default


# ── Technical Analyst ─────────────────────────────────────────────────────────


async def run_technical_analyst(state: FinSightState) -> dict[str, Any]:
    """
    Technical Analyst agent: price action, indicators, chart patterns, options market.
    Uses Alpha Vantage + Yahoo Finance + Python Executor MCP tools.
    """
    ticker = state["ticker"]
    analysis_id = state["analysis_id"]
    t_start = time.time()

    episodic = state.get("episodic_context") or ""
    system_prompt = inject_context(
        TECHNICAL_ANALYST_SYSTEM, ticker=ticker, episodic_context=episodic
    )
    callback = _get_langfuse_callback("technical_analyst", analysis_id)
    llm = _get_llm()

    tools = await _load_tools_from_servers(
        [
            "mcp_servers.alpha_vantage",
            "mcp_servers.yahoo_finance",
            "mcp_servers.python_executor",
        ]
    )

    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(
            content=(
                f"Conduct a thorough technical analysis of {ticker}. "
                f"Fetch all key indicators (RSI, MACD, Bollinger Bands, SMA 50/200, ATR). "
                f"Identify the primary trend, key support/resistance levels, chart patterns. "
                f"Analyze the options market (IV rank, put/call ratio, unusual activity). "
                f"Use the Python executor to compute any custom correlations or statistics needed."
            )
        ),
    ]

    try:
        llm_with_tools = llm.bind_tools(tools) if tools else llm
        callbacks = [callback] if callback else []
        response = await llm_with_tools.ainvoke(messages, config={"callbacks": callbacks})
        content = response.content if hasattr(response, "content") else str(response)

        report = AgentReport(
            agent_name="technical_analyst",
            content=content,
            confidence=_extract_confidence(content),
            tools_used=[t.name for t in tools] if tools else [],
            latency_ms=int((time.time() - t_start) * 1000),
        )
        logger.info("Technical Analyst completed in %.1fs", time.time() - t_start)
        return {"technical_report": report}

    except Exception as exc:
        logger.error("Technical Analyst failed: %s", exc)
        return {
            "technical_report": AgentReport(
                agent_name="technical_analyst",
                content=f"Agent failed: {exc}",
                confidence=0.0,
                latency_ms=int((time.time() - t_start) * 1000),
            ),
            "error": str(exc),
        }


# ── Risk Assessor ─────────────────────────────────────────────────────────────


async def run_risk_assessor(state: FinSightState) -> dict[str, Any]:
    """
    Risk Assessor: reads all three reports, generates adversarial challenges.
    Returns updated challenges list and optionally initiates debate responses.
    """
    analysis_id = state["analysis_id"]

    market = state.get("market_report")
    fundamental = state.get("fundamental_report")
    technical = state.get("technical_report")

    # Build report summaries for the prompt
    market_text = market.content if market else "Not yet available."
    fundamental_text = fundamental.content if fundamental else "Not yet available."
    technical_text = technical.content if technical else "Not yet available."

    system_prompt = inject_context(
        RISK_ASSESSOR_SYSTEM,
        market_report=market_text[:3000],
        fundamental_report=fundamental_text[:3000],
        technical_report=technical_text[:3000],
    )

    callback = _get_langfuse_callback("risk_assessor", analysis_id)
    llm = _get_llm()

    try:
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(
                content=(
                    "Review all three research reports and produce your challenge list. "
                    "Return ONLY valid JSON as specified - no additional text outside the JSON block."
                )
            ),
        ]
        callbacks = [callback] if callback else []
        response = await llm.ainvoke(messages, config={"callbacks": callbacks})
        content = response.content if hasattr(response, "content") else str(response)

        # Parse the JSON challenges from the response
        challenges: list[Challenge] = []
        assessment = "PROCEED"
        try:
            # Extract JSON block from response
            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            if json_match:
                parsed = json.loads(json_match.group())
                assessment = parsed.get("overall_assessment", "PROCEED")

                for ch_data in parsed.get("challenges", []):
                    challenges.append(
                        Challenge(
                            to_agent=ch_data.get("to_agent", "market_researcher"),
                            debate_round=state.get("debate_rounds", 0) + 1,
                            question=ch_data.get("question", ""),
                            cited_claim=ch_data.get("cited_claim", ""),
                            supporting_evidence=ch_data.get("supporting_evidence", ""),
                        )
                    )
        except (json.JSONDecodeError, KeyError) as exc:
            logger.warning("Risk Assessor JSON parse failed: %s — using empty challenges", exc)

        existing = state.get("challenges") or []
        logger.info(
            "Risk Assessor found %d challenges. Assessment: %s",
            len(challenges),
            assessment,
        )
        return {
            "challenges": existing + challenges,
            "current_phase": "debate" if challenges else "strategy",
        }

    except Exception as exc:
        logger.error("Risk Assessor failed: %s", exc)
        return {"challenges": state.get("challenges") or [], "error": str(exc)}


# ── Debate Response Loop ──────────────────────────────────────────────────────


async def run_debate_responses(state: FinSightState) -> dict[str, Any]:
    """
    Each challenged agent responds to its challenges.
    Updates the challenge objects with responses, then re-evaluates.
    """
    challenges = state.get("challenges") or []
    unresolved = [c for c in challenges if not c.resolved]

    if not unresolved:
        return {"current_phase": "strategy"}

    ticker = state["ticker"]
    analysis_id = state["analysis_id"]
    llm = _get_llm()

    # Group challenges by target agent
    by_agent: dict[str, list[Challenge]] = {}
    for ch in unresolved:
        by_agent.setdefault(ch.to_agent, []).append(ch)

    # Get the relevant report text for each agent's response context
    report_map = {
        "market_researcher": (
            state.get("market_report")
            or AgentReport(agent_name="market_researcher", content="", confidence=0)
        ).content,
        "fundamental_analyst": (
            state.get("fundamental_report")
            or AgentReport(agent_name="fundamental_analyst", content="", confidence=0)
        ).content,
        "technical_analyst": (
            state.get("technical_report")
            or AgentReport(agent_name="technical_analyst", content="", confidence=0)
        ).content,
    }

    updated_challenges = list(state.get("challenges") or [])

    for agent_name, agent_challenges in by_agent.items():
        report_text = report_map.get(agent_name, "")
        callback = _get_langfuse_callback(f"debate_{agent_name}", analysis_id)

        challenge_text = "\n\n".join(
            [
                f"**Challenge {i + 1} (Severity: {ch.cited_claim[:100] if ch.cited_claim else 'unspecified'}):**\n"
                f"Cited claim: {ch.cited_claim}\n"
                f"Question: {ch.question}\n"
                f"Counter-evidence: {ch.supporting_evidence}"
                for i, ch in enumerate(agent_challenges)
            ]
        )

        messages = [
            SystemMessage(
                content=(
                    f"You are the {agent_name.replace('_', ' ').title()} agent. "
                    f"Your previous report on {ticker} is shown below. "
                    f"The Risk Assessor has raised challenges you must respond to. "
                    f"Address each challenge directly with specific evidence and data. "
                    f"Maintain or revise your position based on the counter-evidence.\n\n"
                    f"**Your Previous Report (excerpt):**\n{report_text[:2000]}"
                )
            ),
            HumanMessage(content=f"Please respond to these challenges:\n\n{challenge_text}"),
        ]
        try:
            callbacks = [callback] if callback else []
            response = await llm.ainvoke(messages, config={"callbacks": callbacks})
            response_text = response.content if hasattr(response, "content") else str(response)

            # Mark challenges as resolved with response
            for ch in agent_challenges:
                for i, existing_ch in enumerate(updated_challenges):
                    if existing_ch.id == ch.id:
                        updated_challenges[i] = Challenge(
                            **{
                                **ch.model_dump(),
                                "response": response_text[:1500],
                                "resolved": True,
                            }
                        )
        except Exception as exc:
            logger.error("Debate response failed for %s: %s", agent_name, exc)

    debate_rounds = state.get("debate_rounds", 0) + 1
    max_rounds = state.get("max_debate_rounds", 2)

    return {
        "challenges": updated_challenges,
        "debate_rounds": debate_rounds,
        "current_phase": "strategy" if debate_rounds >= max_rounds else "debate",
    }


# ── Portfolio Strategist ──────────────────────────────────────────────────────


async def run_portfolio_strategist(state: FinSightState) -> dict[str, Any]:
    """
    Portfolio Strategist: synthesizes all research + debate into a final
    BUY/HOLD/SELL recommendation with scenarios and options consideration.
    """
    ticker = state["ticker"]
    analysis_id = state["analysis_id"]
    t_start = time.time()

    market = state.get("market_report")
    fundamental = state.get("fundamental_report")
    technical = state.get("technical_report")
    challenges = state.get("challenges") or []

    # Build debate summary
    resolved = [c for c in challenges if c.resolved]
    debate_summary = ""
    if resolved:
        parts = []
        for ch in resolved[:5]:
            parts.append(
                f"• {ch.to_agent}: '{ch.cited_claim[:100]}' → Response: {(ch.response or '')[:300]}"
            )
        debate_summary = (
            "Debate resolved " + str(len(resolved)) + " challenges:\n" + "\n".join(parts)
        )
    else:
        debate_summary = "No challenges raised by Risk Assessor."

    system_prompt = inject_context(
        PORTFOLIO_STRATEGIST_SYSTEM,
        market_report=(market.content if market else "Unavailable")[:2500],
        fundamental_report=(fundamental.content if fundamental else "Unavailable")[:2500],
        technical_report=(technical.content if technical else "Unavailable")[:2500],
        debate_summary=debate_summary,
        portfolio_context="Paper trading account via Alpaca. Risk tolerance: moderate. Max position size: 5% of portfolio.",
    )

    callback = _get_langfuse_callback("portfolio_strategist", analysis_id)
    llm = _get_llm()

    try:
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(
                content=(
                    f"Synthesize all research on {ticker} and produce the final recommendation JSON. "
                    f"Return ONLY the JSON object — no surrounding text or markdown."
                )
            ),
        ]
        callbacks = [callback] if callback else []
        response = await llm.ainvoke(messages, config={"callbacks": callbacks})
        content = response.content if hasattr(response, "content") else str(response)

        # Parse recommendation JSON
        recommendation: TradeRecommendation | None = None
        try:
            json_match = re.search(r"\{.*\}", content, re.DOTALL)
            if json_match:
                data = json.loads(json_match.group())
                scenarios = [
                    ScenarioTarget(**s) for s in data.get("scenarios", []) if isinstance(s, dict)
                ]
                catalysts = [
                    Catalyst(**c) for c in data.get("catalysts", []) if isinstance(c, dict)
                ]
                recommendation = TradeRecommendation(
                    action=data.get("action", "HOLD"),
                    confidence=float(data.get("confidence", 0.5)),
                    entry_price=data.get("entry_price"),
                    stop_loss=data.get("stop_loss"),
                    take_profit=data.get("take_profit"),
                    time_horizon=data.get("time_horizon", "1-3 months"),
                    reasoning_summary=data.get("reasoning_summary", ""),
                    scenarios=scenarios,
                    catalysts=catalysts,
                    risk_factors=data.get("risk_factors", []),
                )
        except (json.JSONDecodeError, Exception) as exc:
            logger.warning(
                "Portfolio Strategist JSON parse failed: %s — creating HOLD default", exc
            )
            recommendation = TradeRecommendation(
                action="HOLD",
                confidence=0.5,
                reasoning_summary=f"JSON parse failed. Raw response excerpt: {content[:500]}",
            )

        logger.info(
            "Portfolio Strategist: %s with %.0f%% confidence (%.1fs)",
            recommendation.action if recommendation else "UNKNOWN",
            (recommendation.confidence if recommendation else 0) * 100,
            time.time() - t_start,
        )

        # Update memory with the final recommendation
        await _save_episodic_memory(
            ticker,
            f"[Recommendation: {recommendation.action if recommendation else 'HOLD'}] "
            f"Confidence: {(recommendation.confidence if recommendation else 0):.0%} | "
            f"Reasoning: {(recommendation.reasoning_summary if recommendation else '')[:200]}",
        )

        return {
            "recommendation": recommendation,
            "current_phase": "complete",
        }

    except Exception as exc:
        logger.error("Portfolio Strategist failed: %s", exc)
        return {
            "recommendation": TradeRecommendation(action="HOLD", confidence=0.0),
            "error": str(exc),
        }
