"""
QuantAgents — POST /api/trade endpoint
Triggers a full analysis + backtest validation + trade execution.
Wraps graph_v3 with SSE streaming support.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from db.base import get_db
from orchestrator.graph_v3 import get_graph_v3
from orchestrator.state import initial_state

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["trade"])


class TradeRequest(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=10)
    user_id: str = Field("default")
    query: str | None = None
    auto_execute: bool = Field(
        False, description="If true, Trade Executor will place orders automatically"
    )
    stream: bool = Field(True)


class TradeResponse(BaseModel):
    analysis_id: str
    ticker: str
    recommendation: str | None
    confidence: float | None
    order_placed: bool
    order_id: str | None
    order_details: dict[str, Any] | None
    backtest_validated: bool | None
    latency_ms: int | None
    created_at: str


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


async def _stream_trade(ticker: str, user_id: str, query: str | None, analysis_id: str):
    t_start = datetime.utcnow()
    yield _sse("trade_started", {"analysis_id": analysis_id, "ticker": ticker})

    state = initial_state(ticker, user_id, query)
    state["analysis_id"] = analysis_id
    graph = get_graph_v3()

    try:
        async for chunk in graph.astream(state, stream_mode="updates"):
            for node_name, node_output in chunk.items():
                if node_name == "load_memory":
                    yield _sse(
                        "memory_loaded", {"has_episodic": bool(node_output.get("episodic_context"))}
                    )

                elif node_name == "load_rl_context":
                    yield _sse("rl_context_loaded", {"has_rl": bool(node_output.get("rl_context"))})

                elif node_name in ("market_researcher", "fundamental_analyst", "technical_analyst"):
                    key_map = {
                        "market_researcher": "market_report",
                        "fundamental_analyst": "fundamental_report",
                        "technical_analyst": "technical_report",
                    }
                    report = node_output.get(key_map[node_name])
                    yield _sse(
                        "agent_complete",
                        {
                            "agent": node_name,
                            "confidence": report.confidence if report else None,
                        },
                    )

                elif node_name == "risk_assessor":
                    chals = node_output.get("challenges") or []
                    yield _sse(
                        "debate_started",
                        {"challenge_count": len([c for c in chals if not c.resolved])},
                    )

                elif node_name == "debate_responses":
                    yield _sse("debate_round", {"round": node_output.get("debate_rounds", 0)})

                elif node_name == "portfolio_strategist":
                    rec = node_output.get("recommendation")
                    yield _sse(
                        "recommendation_ready",
                        {
                            "action": rec.action if rec else None,
                            "confidence": rec.confidence if rec else None,
                        },
                    )

                elif node_name == "backtest_engine":
                    bt = node_output.get("backtest_result")
                    yield _sse(
                        "backtest_complete",
                        {
                            "validated": bt.validated if bt else None,
                            "sharpe": bt.sharpe_ratio if bt else None,
                            "rejection_reason": bt.rejection_reason if bt else None,
                        },
                    )

                elif node_name == "trade_executor":
                    yield _sse(
                        "trade_executed",
                        {
                            "order_placed": node_output.get("order_placed", False),
                            "order_id": node_output.get("order_id"),
                            "details": node_output.get("order_details", {}),
                        },
                    )

                elif node_name == "save_memory":
                    latency = int((datetime.utcnow() - t_start).total_seconds() * 1000)
                    yield _sse(
                        "trade_complete",
                        {
                            "analysis_id": analysis_id,
                            "ticker": ticker,
                            "latency_ms": latency,
                        },
                    )

    except Exception as exc:
        logger.error("Trade stream error for %s: %s", ticker, exc, exc_info=True)
        yield _sse("error", {"analysis_id": analysis_id, "error": str(exc)})


@router.post("/trade")
async def trade(
    request: TradeRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Full pipeline: research → debate → strategy → backtest validation → order execution.

    Returns SSE stream or JSON depending on `stream` flag.
    The Trade Executor will only place orders if `auto_execute=true` AND backtest validation passes.
    """
    ticker = request.ticker.upper().strip()
    analysis_id = str(uuid.uuid4())

    if request.stream:
        return StreamingResponse(
            _stream_trade(ticker, request.user_id, request.query, analysis_id),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Analysis-ID": analysis_id},
        )

    # Non-streaming
    try:
        t_start = datetime.utcnow()
        state = initial_state(ticker, request.user_id, request.query)
        state["analysis_id"] = analysis_id
        graph = get_graph_v3()
        final = await graph.ainvoke(state)
        latency_ms = int((datetime.utcnow() - t_start).total_seconds() * 1000)

        rec = final.get("recommendation")
        bt = final.get("backtest_result")

        return TradeResponse(
            analysis_id=analysis_id,
            ticker=ticker,
            recommendation=rec.action if rec else None,
            confidence=rec.confidence if rec else None,
            order_placed=final.get("order_placed", False),
            order_id=final.get("order_id"),
            order_details=final.get("order_details"),
            backtest_validated=bt.validated if bt else None,
            latency_ms=latency_ms,
            created_at=t_start.isoformat(),
        )
    except Exception as exc:
        logger.error("Trade endpoint failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
