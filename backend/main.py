"""
QuantAgents — FastAPI Application Entry Point
"""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import get_settings
from db.base import init_db

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle."""
    settings = get_settings()
    logger.info(
        "QuantAgents backend starting", environment="paper" if settings.is_paper_trading else "live"
    )
    try:
        await init_db()
    except Exception as e:
        logger.warning(
            f"Failed to connect to database on startup. Make sure Docker is running. Error: {e}"
        )
    yield
    logger.info("QuantAgents backend shutting down")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="QuantAgents API",
        description="Multi-Agent Trading Intelligence Platform",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routes (will grow per phase) ──────────────────────────
    from api.analyze import router as analyze_router
    from api.health import router as health_router
    from api.mock_trade import router as mock_trade_router
    from api.trade import router as trade_router
    from api.ws_analyze import router as ws_router

    app.include_router(health_router, tags=["health"])
    app.include_router(analyze_router)
    app.include_router(ws_router)
    app.include_router(trade_router)
    app.include_router(mock_trade_router)

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=get_settings().backend_port, reload=True)
