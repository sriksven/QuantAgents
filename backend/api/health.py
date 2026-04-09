"""Health check router."""
import time

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from db.base import get_db

router = APIRouter()

_start_time = time.time()


@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    """Returns service health information."""
    try:
        await db.execute(text("SELECT 1"))
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {e}"

    return {
        "status": "ok",
        "uptime_seconds": round(time.time() - _start_time, 2),
        "database": db_status,
        "version": "0.1.0",
    }
