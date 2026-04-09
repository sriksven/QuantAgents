"""
QuantAgents — LangGraph Graph Nodes (Phase 3)
Node functions for the v1 orchestrator: memory loading + 2 research agents.
"""
from __future__ import annotations

import logging
import time
from typing import Any

from langchain_openai import ChatOpenAI
from langfuse.langchain import CallbackHandler as LangfuseCallback

from config import get_settings
from orchestrator.state import AgentReport, FinSightState
from orchestrator.prompts import (
    FUNDAMENTAL_ANALYST_SYSTEM,
    MARKET_RESEARCHER_SYSTEM,
    inject_context,
)

logger = logging.getLogger(__name__)


def _get_langfuse_callback(trace_name: str, analysis_id: str) -> LangfuseCallback | None:
    """Returns Langfuse callback if configured, otherwise None."""
    settings = get_settings()
    if not settings.langfuse_public_key:
        return None
    try:
        return LangfuseCallback(
            trace_name=trace_name,
            metadata={"analysis_id": analysis_id},
        )
    except Exception as exc:
        logger.warning("Langfuse callback init failed: %s", exc)
        return None


def _get_llm(model: str | None = None) -> ChatOpenAI:
    settings = get_settings()
    return ChatOpenAI(
        model=model or settings.openai_model,
        api_key=settings.openai_api_key,
        temperature=0.1,
        max_tokens=4096,
    )


# ── Memory Tools ──────────────────────────────────────────────────────────────

async def _load_episodic_memory(ticker: str) -> str:
    """Load past analyses for this ticker from Redis."""
    try:
        import redis.asyncio as aioredis
        settings = get_settings()
        r = aioredis.from_url(settings.redis_url, decode_responses=True)
        key = f"quantagents:memory:{ticker.upper()}:history"
        history = await r.lrange(key, 0, 4)  # last 5 analyses
        await r.aclose()
        if not history:
            return ""
        summaries = "\n\n".join(history)
        return f"## Past Analyses for {ticker}\n{summaries}"
    except Exception as exc:
        logger.warning("Episodic memory load failed for %s: %s", ticker, exc)
        return ""


async def _save_episodic_memory(ticker: str, summary: str) -> None:
    """Save analysis summary to Redis."""
    try:
        import redis.asyncio as aioredis
        settings = get_settings()
        r = aioredis.from_url(settings.redis_url, decode_responses=True)
        key = f"quantagents:memory:{ticker.upper()}:history"
        await r.lpush(key, summary)
        await r.ltrim(key, 0, 4)  # keep last 5
        await r.aclose()
    except Exception as exc:
        logger.warning("Episodic memory save failed for %s: %s", ticker, exc)


async def _load_semantic_memory(ticker: str, query: str) -> str:
    """Query Qdrant for semantically similar past insights."""
    try:
        from langchain_openai import OpenAIEmbeddings
        from qdrant_client import QdrantClient
        settings = get_settings()

        embeddings = OpenAIEmbeddings(api_key=settings.openai_api_key)
        query_vec = await embeddings.aembed_query(f"{ticker} {query}")

        client = QdrantClient(url=settings.qdrant_url)
        results = client.search(
            collection_name=settings.qdrant_collection,
            query_vector=query_vec,
            limit=5,
            score_threshold=0.75,
        )
        client.close()

        if not results:
            return ""
        context_parts = []
        for r in results:
            payload = r.payload or {}
            context_parts.append(
                f"[{payload.get('ticker', '')} | {payload.get('date', '')} | {payload.get('agent', '')}] "
                f"{payload.get('finding', '')}"
            )
        return "## Semantically Related Past Insights\n" + "\n".join(context_parts)
    except Exception as exc:
        logger.warning("Semantic memory load failed: %s", exc)
        return ""


# ── Node Functions ────────────────────────────────────────────────────────────

async def load_memory(state: FinSightState) -> dict[str, Any]:
    """
    Load episodic and semantic memory context before analysis starts.
    Injects context into state for use by all agents.
    """
    ticker = state["ticker"]
    query = state.get("query") or f"{ticker} stock investment analysis"

    episodic, semantic = await _load_episodic_memory(ticker), await _load_semantic_memory(ticker, query)

    logger.info(
        "Memory loaded for %s: episodic=%d chars, semantic=%d chars",
        ticker, len(episodic), len(semantic),
    )
    return {
        "episodic_context": episodic or None,
        "semantic_context": semantic or None,
        "current_phase": "research",
    }


async def run_market_researcher(state: FinSightState) -> dict[str, Any]:
    """
    Run the Market Researcher agent.
    Uses Tavily + Crawl4AI MCP tools for news and web research.
    """
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from langchain_mcp_adapters.tools import load_mcp_tools

    ticker = state["ticker"]
    analysis_id = state["analysis_id"]
    t_start = time.time()

    # Build system prompt with episodic context
    episodic = state.get("episodic_context") or ""
    system_prompt = inject_context(
        MARKET_RESEARCHER_SYSTEM,
        ticker=ticker,
        episodic_context=episodic,
    )

    callback = _get_langfuse_callback("market_researcher", analysis_id)
    llm = _get_llm()

    try:
        from langchain_core.messages import SystemMessage, HumanMessage
        from langchain.agents import create_tool_calling_agent, AgentExecutor

        # Load tools from MCP servers
        tavily_params = StdioServerParameters(
            command="python",
            args=["-m", "mcp_servers.tavily_news"],
        )
        tools = []
        try:
            async with stdio_client(tavily_params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools = await load_mcp_tools(session)
        except Exception as exc:
            logger.warning("Could not load MCP tools for market researcher: %s", exc)

        # Build prompt and run agent
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"Conduct a thorough market research analysis on {ticker}. Use your tools to search for recent news, sector developments, and macro factors."),
        ]

        if tools:
            llm_with_tools = llm.bind_tools(tools)
        else:
            llm_with_tools = llm

        callbacks = [callback] if callback else []
        response = await llm_with_tools.ainvoke(messages, config={"callbacks": callbacks})
        content = response.content if hasattr(response, "content") else str(response)

        # Extract confidence from response (simple heuristic)
        confidence = 0.65
        if "confidence" in content.lower():
            import re
            match = re.search(r"confidence[:\s]+(\d+)%", content, re.IGNORECASE)
            if match:
                confidence = float(match.group(1)) / 100

        report = AgentReport(
            agent_name="market_researcher",
            content=content,
            confidence=confidence,
            tools_used=["search_news", "get_article_content"] if tools else [],
            latency_ms=int((time.time() - t_start) * 1000),
        )
        logger.info("Market Researcher completed in %.1fs with confidence=%.0f%%", time.time() - t_start, confidence * 100)
        return {"market_report": report}

    except Exception as exc:
        logger.error("Market Researcher failed: %s", exc)
        error_report = AgentReport(
            agent_name="market_researcher",
            content=f"Agent failed: {exc}. Analysis incomplete.",
            confidence=0.0,
            latency_ms=int((time.time() - t_start) * 1000),
        )
        return {"market_report": error_report, "error": str(exc)}


async def run_fundamental_analyst(state: FinSightState) -> dict[str, Any]:
    """
    Run the Fundamental Analyst agent.
    Uses Yahoo Finance + SEC EDGAR MCP tools.
    """
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    from langchain_mcp_adapters.tools import load_mcp_tools

    ticker = state["ticker"]
    analysis_id = state["analysis_id"]
    t_start = time.time()

    episodic = state.get("episodic_context") or ""
    system_prompt = inject_context(
        FUNDAMENTAL_ANALYST_SYSTEM,
        ticker=ticker,
        episodic_context=episodic,
    )

    callback = _get_langfuse_callback("fundamental_analyst", analysis_id)
    llm = _get_llm()

    try:
        from langchain_core.messages import SystemMessage, HumanMessage

        # Load tools from Yahoo Finance + SEC EDGAR MCP servers
        tools = []
        for server_module in ["mcp_servers.yahoo_finance", "mcp_servers.sec_edgar"]:
            params = StdioServerParameters(command="python", args=["-m", server_module])
            try:
                async with stdio_client(params) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()
                        tools.extend(await load_mcp_tools(session))
            except Exception as exc:
                logger.warning("Could not load tools from %s: %s", server_module, exc)

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=(
                f"Conduct a thorough fundamental analysis of {ticker}. "
                f"Pull the latest financial statements, key ratios, and SEC filings. "
                f"Assess the company's financial health, valuation, and business quality."
            )),
        ]

        llm_with_tools = llm.bind_tools(tools) if tools else llm
        callbacks = [callback] if callback else []
        response = await llm_with_tools.ainvoke(messages, config={"callbacks": callbacks})
        content = response.content if hasattr(response, "content") else str(response)

        # Extract confidence
        confidence = 0.65
        import re
        match = re.search(r"confidence[:\s]+(\d+)%", content, re.IGNORECASE)
        if match:
            confidence = float(match.group(1)) / 100

        report = AgentReport(
            agent_name="fundamental_analyst",
            content=content,
            confidence=confidence,
            tools_used=[t.name for t in tools] if tools else [],
            latency_ms=int((time.time() - t_start) * 1000),
        )
        logger.info("Fundamental Analyst completed in %.1fs", time.time() - t_start)
        return {"fundamental_report": report}

    except Exception as exc:
        logger.error("Fundamental Analyst failed: %s", exc)
        return {
            "fundamental_report": AgentReport(
                agent_name="fundamental_analyst",
                content=f"Agent failed: {exc}",
                confidence=0.0,
                latency_ms=int((time.time() - t_start) * 1000),
            ),
            "error": str(exc),
        }


async def save_to_memory(state: FinSightState) -> dict[str, Any]:
    """
    After analysis, save key findings to episodic and semantic memory.
    Called at the end of every analysis run.
    """
    ticker = state["ticker"]
    from datetime import datetime

    # Build episodic summary
    rec = state.get("recommendation")
    market = state.get("market_report")
    fundamental = state.get("fundamental_report")

    summary_parts = [f"Date: {datetime.utcnow().strftime('%Y-%m-%d')}"]
    if rec:
        summary_parts.append(f"Recommendation: {rec.action} ({rec.confidence:.0%} confidence)")
    if market:
        summary_parts.append(f"Market: {market.content[:300]}...")
    if fundamental:
        summary_parts.append(f"Fundamental: {fundamental.content[:300]}...")

    summary = "\n".join(summary_parts)
    await _save_episodic_memory(ticker, summary)

    # Save to Qdrant semantic memory
    try:
        from langchain_openai import OpenAIEmbeddings
        from qdrant_client import QdrantClient
        from qdrant_client.models import PointStruct
        import uuid

        settings = get_settings()
        embeddings = OpenAIEmbeddings(api_key=settings.openai_api_key)
        client = QdrantClient(url=settings.qdrant_url)

        # Ensure collection exists
        try:
            client.get_collection(settings.qdrant_collection)
        except Exception:
            from qdrant_client.models import VectorParams, Distance
            client.create_collection(
                settings.qdrant_collection,
                vectors_config=VectorParams(size=1536, distance=Distance.COSINE),
            )

        points = []
        for report in [market, fundamental]:
            if report and len(report.content) > 50:
                vec = await embeddings.aembed_query(report.content[:1000])
                points.append(PointStruct(
                    id=str(uuid.uuid4()),
                    vector=vec,
                    payload={
                        "ticker": ticker,
                        "agent": report.agent_name,
                        "date": datetime.utcnow().strftime("%Y-%m-%d"),
                        "finding": report.content[:500],
                        "confidence": report.confidence,
                    },
                ))
        if points:
            client.upsert(collection_name=settings.qdrant_collection, points=points)
        client.close()
    except Exception as exc:
        logger.warning("Semantic memory save failed: %s", exc)

    return {}
