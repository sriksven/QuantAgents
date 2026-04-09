"""
QuantAgents — Alpaca MCP Server
7 tools for portfolio management, orders, quotes, and positions.
All order tools enforce a paper-trading safety gate by default.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from mcp.server import FastMCP

logger = logging.getLogger(__name__)
mcp = FastMCP("alpaca")


def _get_client(paper: bool = True):
    """Return an authenticated Alpaca TradingClient."""
    from alpaca.trading.client import TradingClient
    api_key = os.getenv("ALPACA_API_KEY", "")
    secret = os.getenv("ALPACA_SECRET_KEY", "")
    if not api_key or not secret:
        raise ValueError("ALPACA_API_KEY and ALPACA_SECRET_KEY must be set")
    # Always paper unless IS_PAPER_TRADING=false AND caller explicitly passes paper=False
    force_paper = os.getenv("IS_PAPER_TRADING", "true").lower() != "false"
    return TradingClient(api_key, secret, paper=force_paper or paper)


def _get_data_client():
    from alpaca.data.historical import StockHistoricalDataClient
    return StockHistoricalDataClient(
        os.getenv("ALPACA_API_KEY", ""),
        os.getenv("ALPACA_SECRET_KEY", ""),
    )


# ── Safety checks ─────────────────────────────────────────────────────────────

def _validate_order(
    symbol: str,
    qty: float,
    notional: float | None,
    max_position_pct: float = 0.05,
) -> tuple[bool, str]:
    """
    Pre-flight safety validation for any order.
    Returns (is_safe, rejection_reason).
    """
    if not symbol or not symbol.isalpha():
        return False, f"Invalid symbol: {symbol}"
    if qty is not None and qty <= 0:
        return False, f"Quantity must be positive, got {qty}"
    if notional is not None and notional <= 0:
        return False, f"Notional must be positive, got {notional}"
    if notional is not None and notional > 50_000:
        return False, f"Single order notional ${notional:,.0f} exceeds $50,000 safety cap"
    return True, ""


# ── Tool 1: Get Account Info ──────────────────────────────────────────────────

@mcp.tool()
def get_account() -> dict[str, Any]:
    """
    Get Alpaca account summary: equity, buying power, positions count, P&L.

    Returns:
        Dict with account_id, equity, buying_power, cash, portfolio_value,
        day_trade_count, pattern_day_trader flag, trading_blocked status.
    """
    try:
        client = _get_client()
        acc = client.get_account()
        return {
            "account_id": str(acc.id),
            "status": str(acc.status),
            "equity": float(acc.equity or 0),
            "last_equity": float(acc.last_equity or 0),
            "buying_power": float(acc.buying_power or 0),
            "cash": float(acc.cash or 0),
            "portfolio_value": float(acc.portfolio_value or 0),
            "day_trade_count": int(acc.daytrade_count or 0),
            "pattern_day_trader": bool(acc.pattern_day_trader),
            "trading_blocked": bool(acc.trading_blocked),
            "account_blocked": bool(acc.account_blocked),
            "day_pl": round(float(acc.equity or 0) - float(acc.last_equity or 0), 2),
            "currency": "USD",
            "is_paper": os.getenv("IS_PAPER_TRADING", "true").lower() != "false",
        }
    except Exception as exc:
        logger.error("get_account failed: %s", exc)
        return {"error": str(exc)}


# ── Tool 2: Get Positions ─────────────────────────────────────────────────────

@mcp.tool()
def get_positions() -> dict[str, Any]:
    """
    Get all current open positions with P&L and portfolio weight.

    Returns:
        Dict with positions list and portfolio summary.
    """
    try:
        client = _get_client()
        positions = client.get_all_positions()
        acc = client.get_account()
        portfolio_value = float(acc.portfolio_value or 1)

        pos_list = []
        total_unrealized_pl = 0.0
        for p in positions:
            unpl = float(p.unrealized_pl or 0)
            mkt_val = float(p.market_value or 0)
            total_unrealized_pl += unpl
            pos_list.append({
                "symbol": str(p.symbol),
                "qty": float(p.qty or 0),
                "side": str(p.side),
                "avg_entry_price": float(p.avg_entry_price or 0),
                "current_price": float(p.current_price or 0),
                "market_value": mkt_val,
                "cost_basis": float(p.cost_basis or 0),
                "unrealized_pl": unpl,
                "unrealized_plpc": float(p.unrealized_plpc or 0),
                "portfolio_weight_pct": round(mkt_val / portfolio_value * 100, 2),
            })

        return {
            "positions": pos_list,
            "position_count": len(pos_list),
            "total_unrealized_pl": round(total_unrealized_pl, 2),
            "portfolio_value": portfolio_value,
        }
    except Exception as exc:
        logger.error("get_positions failed: %s", exc)
        return {"error": str(exc), "positions": []}


# ── Tool 3: Get Quote ─────────────────────────────────────────────────────────

@mcp.tool()
def get_latest_quote(ticker: str) -> dict[str, Any]:
    """
    Get the latest NBBO quote for a stock from Alpaca data feed.

    Args:
        ticker: Stock ticker symbol (e.g., "AAPL")

    Returns:
        Dict with bid, ask, mid, spread, timestamp.
    """
    try:
        from alpaca.data.requests import StockLatestQuoteRequest
        client = _get_data_client()
        req = StockLatestQuoteRequest(symbol_or_symbols=[ticker.upper()])
        quotes = client.get_stock_latest_quote(req)
        q = quotes.get(ticker.upper())
        if not q:
            return {"error": f"No quote for {ticker}", "ticker": ticker}
        bid = float(q.bid_price or 0)
        ask = float(q.ask_price or 0)
        mid = round((bid + ask) / 2, 4) if bid and ask else None
        return {
            "ticker": ticker.upper(),
            "bid": bid,
            "ask": ask,
            "mid": mid,
            "spread": round(ask - bid, 4) if bid and ask else None,
            "spread_bps": round((ask - bid) / mid * 10000, 1) if mid else None,
            "bid_size": int(q.bid_size or 0),
            "ask_size": int(q.ask_size or 0),
            "timestamp": str(q.timestamp),
        }
    except Exception as exc:
        logger.error("get_latest_quote(%s) failed: %s", ticker, exc)
        return {"error": str(exc), "ticker": ticker}


# ── Tool 4: Place Market Order ────────────────────────────────────────────────

@mcp.tool()
def place_market_order(
    ticker: str,
    side: str,
    qty: float | None = None,
    notional: float | None = None,
) -> dict[str, Any]:
    """
    Place a market order. Requires either qty (shares) or notional (dollar amount).
    SAFETY: Runs pre-flight validation. Paper trading enforced unless IS_PAPER_TRADING=false.

    Args:
        ticker: Stock ticker (e.g., "AAPL")
        side: "buy" or "sell"
        qty: Number of shares (fractional supported)
        notional: Dollar notional (alternative to qty)

    Returns:
        Dict with order_id, status, filled details, or rejection reason.
    """
    from alpaca.trading.requests import MarketOrderRequest
    from alpaca.trading.enums import OrderSide, TimeInForce

    side_lower = side.lower()
    if side_lower not in ("buy", "sell"):
        return {"error": f"side must be 'buy' or 'sell', got: {side}"}

    is_safe, reason = _validate_order(ticker, qty or 0, notional)
    if not is_safe:
        return {"error": f"Order rejected by safety check: {reason}", "ticker": ticker}

    try:
        client = _get_client()
        order_side = OrderSide.BUY if side_lower == "buy" else OrderSide.SELL

        req_kwargs: dict[str, Any] = {
            "symbol": ticker.upper(),
            "side": order_side,
            "time_in_force": TimeInForce.DAY,
        }
        if notional is not None:
            req_kwargs["notional"] = round(notional, 2)
        else:
            req_kwargs["qty"] = qty

        order = client.submit_order(MarketOrderRequest(**req_kwargs))

        return {
            "order_id": str(order.id),
            "client_order_id": str(order.client_order_id),
            "ticker": ticker.upper(),
            "side": side_lower,
            "qty": float(order.qty or 0),
            "notional": float(order.notional or 0) if order.notional else None,
            "status": str(order.status),
            "submitted_at": str(order.submitted_at),
            "filled_qty": float(order.filled_qty or 0),
            "filled_avg_price": float(order.filled_avg_price or 0) if order.filled_avg_price else None,
            "is_paper": os.getenv("IS_PAPER_TRADING", "true").lower() != "false",
        }
    except Exception as exc:
        logger.error("place_market_order(%s %s %s) failed: %s", side, ticker, qty or notional, exc)
        return {"error": str(exc), "ticker": ticker}


# ── Tool 5: Place Limit Order ─────────────────────────────────────────────────

@mcp.tool()
def place_limit_order(
    ticker: str,
    side: str,
    qty: float,
    limit_price: float,
    time_in_force: str = "day",
) -> dict[str, Any]:
    """
    Place a limit order.
    SAFETY: Pre-flight validation, paper trading enforced.

    Args:
        ticker: Stock ticker
        side: "buy" or "sell"
        qty: Number of shares
        limit_price: Limit price in USD
        time_in_force: "day" or "gtc"

    Returns:
        Dict with order_id, status, limit price.
    """
    from alpaca.trading.requests import LimitOrderRequest
    from alpaca.trading.enums import OrderSide, TimeInForce

    side_lower = side.lower()
    if side_lower not in ("buy", "sell"):
        return {"error": f"side must be 'buy' or 'sell', got: {side}"}
    if limit_price <= 0:
        return {"error": f"limit_price must be positive, got {limit_price}"}

    is_safe, reason = _validate_order(ticker, qty, None)
    if not is_safe:
        return {"error": f"Order rejected: {reason}", "ticker": ticker}

    try:
        client = _get_client()
        tif_map = {"day": TimeInForce.DAY, "gtc": TimeInForce.GTC}
        order = client.submit_order(LimitOrderRequest(
            symbol=ticker.upper(),
            qty=qty,
            side=OrderSide.BUY if side_lower == "buy" else OrderSide.SELL,
            limit_price=limit_price,
            time_in_force=tif_map.get(time_in_force.lower(), TimeInForce.DAY),
        ))
        return {
            "order_id": str(order.id),
            "ticker": ticker.upper(),
            "side": side_lower,
            "qty": float(order.qty or 0),
            "limit_price": limit_price,
            "status": str(order.status),
            "submitted_at": str(order.submitted_at),
            "is_paper": os.getenv("IS_PAPER_TRADING", "true").lower() != "false",
        }
    except Exception as exc:
        logger.error("place_limit_order failed: %s", exc)
        return {"error": str(exc), "ticker": ticker}


# ── Tool 6: Cancel Order ──────────────────────────────────────────────────────

@mcp.tool()
def cancel_order(order_id: str) -> dict[str, Any]:
    """
    Cancel an open order by order ID.

    Args:
        order_id: Alpaca order UUID

    Returns:
        Dict with cancellation status.
    """
    try:
        client = _get_client()
        client.cancel_order_by_id(order_id)
        return {"order_id": order_id, "status": "cancelled", "success": True}
    except Exception as exc:
        logger.error("cancel_order(%s) failed: %s", order_id, exc)
        return {"error": str(exc), "order_id": order_id, "success": False}


# ── Tool 7: Get Recent Orders ─────────────────────────────────────────────────

@mcp.tool()
def get_orders(status: str = "all", limit: int = 20) -> dict[str, Any]:
    """
    Get recent orders from Alpaca.

    Args:
        status: "open", "closed", or "all"
        limit: Maximum number of orders to return (max 50)

    Returns:
        Dict with orders list including fill details.
    """
    try:
        from alpaca.trading.requests import GetOrdersRequest
        from alpaca.trading.enums import QueryOrderStatus

        status_map = {
            "open": QueryOrderStatus.OPEN,
            "closed": QueryOrderStatus.CLOSED,
            "all": QueryOrderStatus.ALL,
        }
        client = _get_client()
        req = GetOrdersRequest(
            status=status_map.get(status.lower(), QueryOrderStatus.ALL),
            limit=min(limit, 50),
        )
        orders = client.get_orders(req)
        order_list = []
        for o in orders:
            order_list.append({
                "order_id": str(o.id),
                "symbol": str(o.symbol),
                "side": str(o.side),
                "type": str(o.type),
                "qty": float(o.qty or 0),
                "filled_qty": float(o.filled_qty or 0),
                "filled_avg_price": float(o.filled_avg_price) if o.filled_avg_price else None,
                "status": str(o.status),
                "submitted_at": str(o.submitted_at),
                "filled_at": str(o.filled_at) if o.filled_at else None,
            })
        return {"orders": order_list, "count": len(order_list)}
    except Exception as exc:
        logger.error("get_orders failed: %s", exc)
        return {"error": str(exc), "orders": []}


if __name__ == "__main__":
    mcp.run()
