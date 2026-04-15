"""
QuantAgents — POST /api/analyze endpoint
Triggers a full multi-agent analysis for a ticker.
Supports both streaming (SSE) and non-streaming (JSON) responses.
"""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import AsyncGenerator
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from db.base import get_db
from db.models import AgentReport as AgentReportModel
from db.models import Analysis
from orchestrator.graph import get_graph
from orchestrator.state import initial_state

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["analyze"])


# ── Request / Response models ─────────────────────────────────────────────────


class AnalyzeRequest(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=10, description="Stock ticker symbol")
    user_id: str = Field("default", description="User identifier")
    query: str | None = Field(None, description="Optional research focus override")
    stream: bool = Field(True, description="Stream intermediate results via SSE")


class AnalyzeResponse(BaseModel):
    analysis_id: str
    ticker: str
    status: str
    recommendation: str | None
    confidence: float | None
    market_report: str | None
    fundamental_report: str | None
    latency_ms: int | None
    created_at: str


# ── SSE Streaming helper ──────────────────────────────────────────────────────


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def run_streaming_analysis(
    ticker: str,
    user_id: str,
    query: str | None,
    analysis_id: str,
    db: AsyncSession,
) -> AsyncGenerator[str, None]:
    """
    Execute the LangGraph workflow and stream progress events via SSE.
    Events: analysis_started, phase_started, agent_complete, analysis_complete, error
    """
    t_start = datetime.utcnow()

    yield _sse_event(
        "analysis_started",
        {
            "analysis_id": analysis_id,
            "ticker": ticker.upper(),
            "timestamp": t_start.isoformat(),
        },
    )

    # Persist to DB
    analysis_row = Analysis(
        id=uuid.UUID(analysis_id),
        ticker=ticker.upper(),
        user_id=user_id,
        status="running",
    )
    db.add(analysis_row)
    await db.commit()

    state = initial_state(ticker, user_id, query)
    state["analysis_id"] = analysis_id
    graph = get_graph()

    try:
        yield _sse_event(
            "phase_started",
            {"phase": "research", "agents": ["market_researcher", "fundamental_analyst"]},
        )

        # Stream from LangGraph
        async for chunk in graph.astream(state, stream_mode="updates"):
            for node_name, node_output in chunk.items():
                if node_name == "load_memory":
                    yield _sse_event(
                        "memory_loaded",
                        {
                            "has_episodic": bool(node_output.get("episodic_context")),
                            "has_semantic": bool(node_output.get("semantic_context")),
                        },
                    )

                elif node_name == "market_researcher":
                    report = node_output.get("market_report")
                    if report:
                        yield _sse_event(
                            "agent_complete",
                            {
                                "agent": "market_researcher",
                                "confidence": report.confidence
                                if hasattr(report, "confidence")
                                else getattr(report, "confidence", None),
                                "content_preview": (
                                    report.content if hasattr(report, "content") else ""
                                )[:200],
                            },
                        )

                elif node_name == "fundamental_analyst":
                    report = node_output.get("fundamental_report")
                    if report:
                        yield _sse_event(
                            "agent_complete",
                            {
                                "agent": "fundamental_analyst",
                                "confidence": report.confidence
                                if hasattr(report, "confidence")
                                else None,
                                "content_preview": (
                                    report.content if hasattr(report, "content") else ""
                                )[:200],
                            },
                        )

        # Extract final state
        final_state = (
            await graph.ainvoke(state) if False else state
        )  # state is mutated in place by astream
        # Re-run once more to capture final state correctly
        async for chunk in graph.astream(state, stream_mode="values"):
            final_state = chunk  # last chunk = final state

        market_report = final_state.get("market_report")
        fundamental_report = final_state.get("fundamental_report")
        recommendation = final_state.get("recommendation")

        latency_ms = int((datetime.utcnow() - t_start).total_seconds() * 1000)

        # Update DB
        analysis_row.status = "complete"
        analysis_row.recommendation = recommendation.action if recommendation else None
        analysis_row.confidence = recommendation.confidence if recommendation else None
        analysis_row.latency_ms = latency_ms
        analysis_row.completed_at = datetime.utcnow()

        # Persist agent reports
        for report in [market_report, fundamental_report]:
            if report:
                db.add(
                    AgentReportModel(
                        id=uuid.uuid4(),
                        analysis_id=uuid.UUID(analysis_id),
                        agent_name=report.agent_name,
                        content=report.content,
                        confidence=report.confidence,
                        tools_used=report.tools_used,
                        latency_ms=report.latency_ms,
                    )
                )

        await db.commit()

        yield _sse_event(
            "analysis_complete",
            {
                "analysis_id": analysis_id,
                "ticker": ticker.upper(),
                "recommendation": recommendation.action if recommendation else None,
                "confidence": recommendation.confidence if recommendation else None,
                "latency_ms": latency_ms,
            },
        )

    except Exception as exc:
        logger.error("Analysis %s failed: %s", analysis_id, exc, exc_info=True)
        analysis_row.status = "error"
        analysis_row.error_message = str(exc)
        await db.commit()

        yield _sse_event("error", {"analysis_id": analysis_id, "error": str(exc)})


# ── API Endpoints ─────────────────────────────────────────────────────────────


@router.post("/analyze")
async def analyze(
    request: AnalyzeRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Run a full multi-agent analysis for a ticker.

    Returns:
    - If `stream=true`: SSE stream with real-time progress events
    - If `stream=false`: JSON response after completion
    """
    ticker = request.ticker.upper().strip()
    analysis_id = str(uuid.uuid4())

    if request.stream:
        return StreamingResponse(
            run_streaming_analysis(ticker, request.user_id, request.query, analysis_id, db),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "X-Analysis-ID": analysis_id,
            },
        )
    else:
        # Non-streaming: run and wait
        state = initial_state(ticker, request.user_id, request.query)
        state["analysis_id"] = analysis_id
        graph = get_graph()

        try:
            t_start = datetime.utcnow()
            final = await graph.ainvoke(state)
            latency_ms = int((datetime.utcnow() - t_start).total_seconds() * 1000)

            market = final.get("market_report")
            fundamental = final.get("fundamental_report")
            recommendation = final.get("recommendation")

            return AnalyzeResponse(
                analysis_id=analysis_id,
                ticker=ticker,
                status="complete",
                recommendation=recommendation.action if recommendation else None,
                confidence=recommendation.confidence if recommendation else None,
                market_report=market.content if market else None,
                fundamental_report=fundamental.content if fundamental else None,
                latency_ms=latency_ms,
                created_at=t_start.isoformat(),
            )
        except Exception as exc:
            logger.error("Non-streaming analysis failed: %s", exc, exc_info=True)
            raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/analyze/{analysis_id}")
async def get_analysis(
    analysis_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Get the status and results of a previous analysis by ID."""
    from sqlalchemy import select

    result = await db.execute(select(Analysis).where(Analysis.id == uuid.UUID(analysis_id)))
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(status_code=404, detail=f"Analysis {analysis_id} not found")

    return {
        "analysis_id": str(analysis.id),
        "ticker": analysis.ticker,
        "status": analysis.status,
        "recommendation": analysis.recommendation,
        "confidence": analysis.confidence,
        "latency_ms": analysis.latency_ms,
        "created_at": analysis.created_at.isoformat() if analysis.created_at else None,
        "completed_at": analysis.completed_at.isoformat() if analysis.completed_at else None,
        "error": analysis.error_message,
    }
