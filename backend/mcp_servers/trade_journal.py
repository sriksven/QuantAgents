"""
QuantAgents — Trade Journal MCP Server
Persists and retrieves trade records, P&L summaries, and RL reward signals.
Backed by PostgreSQL via SQLAlchemy (async).
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta
from typing import Any

from mcp.server import FastMCP

logger = logging.getLogger(__name__)
mcp = FastMCP("trade-journal")

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/quantagents"
)


async def _get_conn():
    """Return an asyncpg connection pool."""
    import asyncpg

    url = DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
    return await asyncpg.connect(url)


# ── Tool 1: Log Trade ────────────────────────────────────────────────────────


@mcp.tool()
async def log_trade(
    analysis_id: str,
    ticker: str,
    action: str,
    qty: float,
    price: float,
    order_id: str = "",
    strategy: str = "committee_recommendation",
    confidence: float = 0.0,
    stop_loss: float | None = None,
    take_profit: float | None = None,
) -> dict[str, Any]:
    """
    Record a trade execution in the journal.

    Args:
        analysis_id: UUID of the analysis that triggered this trade
        ticker: Stock ticker
        action: "BUY", "SELL", or "HOLD"
        qty: Number of shares traded
        price: Execution price
        order_id: Alpaca order UUID (optional)
        strategy: Strategy description
        confidence: Agent confidence score [0,1]
        stop_loss: Stop loss price (optional)
        take_profit: Take profit target (optional)

    Returns:
        Dict with trade_id and logged fields.
    """
    import uuid

    trade_id = str(uuid.uuid4())
    try:
        conn = await _get_conn()
        await conn.execute(
            """
            INSERT INTO trade_journal
            (id, analysis_id, ticker, action, qty, price, order_id, strategy,
             confidence, stop_loss, take_profit, created_at)
            VALUES ($1, $2::uuid, $3, $4, $5, $6, $7, $8, $9, $10, $11, NOW())
        """,
            trade_id,
            analysis_id,
            ticker.upper(),
            action.upper(),
            qty,
            price,
            order_id or None,
            strategy,
            confidence,
            stop_loss,
            take_profit,
        )
        await conn.close()
        return {
            "trade_id": trade_id,
            "ticker": ticker.upper(),
            "action": action.upper(),
            "qty": qty,
            "price": price,
            "notional": round(qty * price, 2),
            "logged": True,
        }
    except Exception as exc:
        logger.error("log_trade failed: %s", exc)
        return {"error": str(exc), "trade_id": trade_id, "logged": False}


# ── Tool 2: Update Trade Outcome ─────────────────────────────────────────────


@mcp.tool()
async def update_trade_outcome(
    trade_id: str,
    exit_price: float,
    exit_date: str = "",
    notes: str = "",
) -> dict[str, Any]:
    """
    Update a trade with its actual exit price to compute realized P&L and RL reward.

    Args:
        trade_id: UUID of the trade journal entry
        exit_price: Actual exit price per share
        exit_date: ISO date of exit (defaults to today)
        notes: Optional notes

    Returns:
        Dict with realized_pnl, return_pct, reward_signal, and holding_days.
    """
    try:
        conn = await _get_conn()
        row = await conn.fetchrow(
            "SELECT ticker, action, qty, price, created_at FROM trade_journal WHERE id = $1",
            trade_id,
        )
        if not row:
            await conn.close()
            return {"error": f"Trade {trade_id} not found"}

        entry_price = float(row["price"])
        qty = float(row["qty"])
        action = str(row["action"])
        created_at: datetime = row["created_at"]

        # P&L (positive for profitable trades)
        if action == "BUY":
            realized_pnl = (exit_price - entry_price) * qty
            return_pct = (exit_price - entry_price) / entry_price
        elif action == "SELL":  # short sale
            realized_pnl = (entry_price - exit_price) * qty
            return_pct = (entry_price - exit_price) / entry_price
        else:
            realized_pnl = 0.0
            return_pct = 0.0

        holding_days = (datetime.utcnow() - created_at).days

        # RL reward signal: scaled return (reward engineering)
        # Positive reward for profit, negative for loss, dampened by holding period
        base_reward = return_pct * 100
        time_penalty = max(0, (holding_days - 90) * 0.1)  # penalize holding > 90 days
        reward_signal = base_reward - time_penalty

        await conn.execute(
            """
            UPDATE trade_journal
            SET exit_price = $1, exit_date = $2::date, realized_pnl = $3,
                return_pct = $4, reward_signal = $5, holding_days = $6,
                notes = $7, updated_at = NOW()
            WHERE id = $8
        """,
            exit_price,
            exit_date or datetime.utcnow().strftime("%Y-%m-%d"),
            round(realized_pnl, 2),
            round(return_pct, 4),
            round(reward_signal, 4),
            holding_days,
            notes,
            trade_id,
        )
        await conn.close()

        return {
            "trade_id": trade_id,
            "ticker": str(row["ticker"]),
            "entry_price": entry_price,
            "exit_price": exit_price,
            "realized_pnl": round(realized_pnl, 2),
            "return_pct": round(return_pct * 100, 2),
            "holding_days": holding_days,
            "reward_signal": round(reward_signal, 4),
            "updated": True,
        }
    except Exception as exc:
        logger.error("update_trade_outcome failed: %s", exc)
        return {"error": str(exc), "trade_id": trade_id}


# ── Tool 3: Get P&L Summary ──────────────────────────────────────────────────


@mcp.tool()
async def get_pnl_summary(days: int = 90, ticker: str = "") -> dict[str, Any]:
    """
    Get realized P&L summary for the last N days, optionally filtered by ticker.

    Args:
        days: Lookback period in days (default 90)
        ticker: Optional ticker filter (empty = all tickers)

    Returns:
        Dict with total_pnl, win_rate, avg_return, best/worst trade, per-ticker breakdown.
    """
    try:
        conn = await _get_conn()
        since = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")

        query_params: list[Any] = [since]
        query = """
            SELECT ticker, action, realized_pnl, return_pct, reward_signal, created_at
            FROM trade_journal
            WHERE created_at >= $1 AND realized_pnl IS NOT NULL
        """
        if ticker:
            query += " AND ticker = $2"
            query_params.append(ticker.upper())

        rows = await conn.fetch(query, *query_params)
        await conn.close()

        if not rows:
            return {"period_days": days, "total_trades": 0, "total_pnl": 0.0}

        pnls = [float(r["realized_pnl"]) for r in rows]
        returns = [float(r["return_pct"]) for r in rows if r["return_pct"] is not None]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]
        rewards = [float(r["reward_signal"]) for r in rows if r["reward_signal"] is not None]

        # Per-ticker breakdown
        ticker_stats: dict[str, dict] = {}
        for r in rows:
            t = str(r["ticker"])
            if t not in ticker_stats:
                ticker_stats[t] = {"trades": 0, "pnl": 0.0, "wins": 0}
            ticker_stats[t]["trades"] += 1
            ticker_stats[t]["pnl"] += float(r["realized_pnl"])
            if float(r["realized_pnl"]) > 0:
                ticker_stats[t]["wins"] += 1

        return {
            "period_days": days,
            "total_trades": len(rows),
            "total_pnl": round(sum(pnls), 2),
            "win_rate": round(len(wins) / len(rows), 3) if rows else 0,
            "avg_return_pct": round(sum(returns) / len(returns) * 100, 2) if returns else 0,
            "best_trade_pnl": round(max(pnls), 2) if pnls else 0,
            "worst_trade_pnl": round(min(pnls), 2) if pnls else 0,
            "gross_profit": round(sum(wins), 2),
            "gross_loss": round(sum(losses), 2),
            "profit_factor": round(sum(wins) / abs(sum(losses)), 3) if losses else None,
            "avg_reward_signal": round(sum(rewards) / len(rewards), 4) if rewards else 0,
            "ticker_breakdown": {
                t: {
                    "trades": s["trades"],
                    "pnl": round(s["pnl"], 2),
                    "win_rate": round(s["wins"] / s["trades"], 2),
                }
                for t, s in ticker_stats.items()
            },
        }
    except Exception as exc:
        logger.error("get_pnl_summary failed: %s", exc)
        return {"error": str(exc)}


# ── Tool 4: Get RL Reward History ─────────────────────────────────────────────


@mcp.tool()
async def get_rl_reward_history(ticker: str, limit: int = 20) -> dict[str, Any]:
    """
    Get the RL reward signal history for a ticker. Used by agents to calibrate
    confidence and adapt prompts.

    Args:
        ticker: Stock ticker
        limit: Number of recent trades to return (max 50)

    Returns:
        Dict with reward signals, avg_reward, 90-day prediction accuracy.
    """
    try:
        conn = await _get_conn()
        rows = await conn.fetch(
            """
            SELECT action, reward_signal, return_pct, confidence, created_at
            FROM trade_journal
            WHERE ticker = $1 AND reward_signal IS NOT NULL
            ORDER BY created_at DESC
            LIMIT $2
        """,
            ticker.upper(),
            min(limit, 50),
        )
        await conn.close()

        if not rows:
            return {"ticker": ticker.upper(), "trade_count": 0, "avg_reward": 0.0, "context": ""}

        rewards = [float(r["reward_signal"]) for r in rows]
        returns = [float(r["return_pct"]) for r in rows if r["return_pct"] is not None]
        # 90-day accuracy: fraction of trades with positive return
        positive = sum(1 for r in returns if r > 0)
        accuracy_90d = round(positive / len(returns), 3) if returns else 0

        # Build context string for agent prompts
        context_lines = []
        for r in rows[:5]:
            context_lines.append(
                f"- {r['action']} on {str(r['created_at'])[:10]}: "
                f"reward={float(r['reward_signal']):.3f}, return={float(r['return_pct'] or 0) * 100:.1f}%, "
                f"confidence_at_time={float(r['confidence'] or 0):.0%}"
            )

        context = (
            f"Last {len(rows)} trades on {ticker.upper()}:\n"
            f"Avg reward: {sum(rewards) / len(rewards):.3f} | 90-day accuracy: {accuracy_90d:.0%}\n"
            + "\n".join(context_lines)
        )

        return {
            "ticker": ticker.upper(),
            "trade_count": len(rows),
            "avg_reward": round(sum(rewards) / len(rewards), 4),
            "accuracy_90d": accuracy_90d,
            "rewards": rewards[:10],
            "context": context,
        }
    except Exception as exc:
        logger.error("get_rl_reward_history(%s) failed: %s", ticker, exc)
        return {"error": str(exc), "ticker": ticker}


if __name__ == "__main__":
    mcp.run()
