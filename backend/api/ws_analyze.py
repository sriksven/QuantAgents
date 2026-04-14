"""
QuantAgents — WebSocket Streaming Endpoint
Provides real-time agent updates via WebSocket for the Analysis Console.
Complements the SSE endpoint with bi-directional support (e.g. cancel mid-run).
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from db.base import get_db
from orchestrator.graph_v2 import get_graph_v2
from orchestrator.state import initial_state

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/ws", tags=["websocket"])

# Track active analysis sessions for cancellation
_active_tasks: dict[str, asyncio.Task] = {}


async def _send(ws: WebSocket, event: str, data: dict[str, Any]) -> None:
    """Send a structured event over WebSocket."""
    try:
        await ws.send_text(json.dumps({"event": event, "data": data, "ts": datetime.utcnow().isoformat()}))
    except Exception:
        pass  # Client may have disconnected


@router.websocket("/analyze/{ticker}")
async def ws_analyze(ws: WebSocket, ticker: str):
    """
    WebSocket endpoint for real-time analysis streaming.
    
    Client sends:
      {"action": "start", "user_id": "...", "query": "..."}
      {"action": "cancel"}
    
    Server sends events:
      analysis_started | memory_loaded | agent_started | agent_complete
      debate_started | debate_round_complete | strategy_complete
      analysis_complete | error
    """
    await ws.accept()
    analysis_id = str(uuid.uuid4())
    ticker = ticker.upper()
    analysis_task: asyncio.Task | None = None

    try:
        # Wait for start command
        raw = await asyncio.wait_for(ws.receive_text(), timeout=30.0)
        msg = json.loads(raw)

        if msg.get("action") != "start":
            await _send(ws, "error", {"message": "Expected {action: 'start'}"})
            return

        user_id = msg.get("user_id", "default")
        query = msg.get("query")

        await _send(ws, "analysis_started", {
            "analysis_id": analysis_id,
            "ticker": ticker,
            "agents": ["market_researcher", "fundamental_analyst", "technical_analyst",
                       "risk_assessor", "portfolio_strategist"],
        })

        state = initial_state(ticker, user_id, query)
        state["analysis_id"] = analysis_id
        graph = get_graph_v2()

        # Stream graph updates
        async def run_analysis():
            try:
                async for chunk in graph.astream(state, stream_mode="updates"):
                    for node_name, node_output in chunk.items():
                        if node_name == "load_memory":
                            await _send(ws, "memory_loaded", {
                                "has_episodic": bool(node_output.get("episodic_context")),
                                "has_semantic": bool(node_output.get("semantic_context")),
                            })

                        elif node_name in ("market_researcher", "fundamental_analyst", "technical_analyst"):
                            key = f"{node_name.split('_')[0]}_report" if "analyst" not in node_name else f"{'_'.join(node_name.split('_')[:2])}_report"
                            # Determine report key
                            report_key_map = {
                                "market_researcher": "market_report",
                                "fundamental_analyst": "fundamental_report",
                                "technical_analyst": "technical_report",
                            }
                            report = node_output.get(report_key_map.get(node_name, ""))
                            await _send(ws, "agent_complete", {
                                "agent": node_name,
                                "confidence": report.confidence if report else None,
                                "latency_ms": report.latency_ms if report else None,
                                "preview": (report.content[:300] if report else "") if isinstance(report, object) and hasattr(report, "content") else "",
                            })

                        elif node_name == "risk_assessor":
                            challenges = node_output.get("challenges") or []
                            new_challenges = [c for c in challenges if not getattr(c, "resolved", False)]
                            await _send(ws, "debate_started", {
                                "challenge_count": len(new_challenges),
                                "assessment": node_output.get("current_phase", "debate"),
                                "challenges": [
                                    {"to": getattr(c, "to_agent", ""), "question": getattr(c, "question", "")[:200]}
                                    for c in new_challenges[:5]
                                ],
                            })

                        elif node_name == "debate_responses":
                            rounds = node_output.get("debate_rounds", 0)
                            challenges = node_output.get("challenges") or []
                            resolved = sum(1 for c in challenges if getattr(c, "resolved", False))
                            await _send(ws, "debate_round_complete", {
                                "round": rounds,
                                "resolved": resolved,
                                "total": len(challenges),
                            })

                        elif node_name == "portfolio_strategist":
                            rec = node_output.get("recommendation")
                            await _send(ws, "strategy_complete", {
                                "action": rec.action if rec else None,
                                "confidence": rec.confidence if rec else None,
                                "reasoning": rec.reasoning_summary if hasattr(rec, "reasoning_summary") else None,
                            })

                        elif node_name == "save_memory":
                            await _send(ws, "analysis_complete", {
                                "analysis_id": analysis_id,
                                "ticker": ticker,
                            })
            except Exception as e:
                logger.error("Internal LangGraph failure during %s: %s", analysis_id, e, exc_info=True)
                await _send(ws, "error", {"message": f"Graph execution failed: {str(e)}"})

        analysis_task = asyncio.create_task(run_analysis())
        _active_tasks[analysis_id] = analysis_task

        # Listen for cancel while running
        async def listen_for_cancel():
            while not analysis_task.done():
                try:
                    raw_cancel = await asyncio.wait_for(ws.receive_text(), timeout=1.0)
                    cancel_msg = json.loads(raw_cancel)
                    if cancel_msg.get("action") == "cancel":
                        analysis_task.cancel()
                        await _send(ws, "cancelled", {"analysis_id": analysis_id})
                        return
                except asyncio.TimeoutError:
                    continue
                except Exception:
                    break

        await asyncio.gather(analysis_task, listen_for_cancel(), return_exceptions=True)

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected for %s/%s", ticker, analysis_id)
        if analysis_task and not analysis_task.done():
            analysis_task.cancel()
    except asyncio.TimeoutError:
        await _send(ws, "error", {"message": "Connection timeout waiting for start command"})
    except Exception as exc:
        logger.error("WebSocket error for %s: %s", ticker, exc, exc_info=True)
        await _send(ws, "error", {"message": str(exc)})
    finally:
        _active_tasks.pop(analysis_id, None)
        try:
            await ws.close()
        except Exception:
            pass
