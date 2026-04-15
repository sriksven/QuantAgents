import logging
from typing import Annotated

import httpx
from config import get_settings
from db.base import get_db
from db.models import MockPortfolio, MockPosition, MockTrade
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/mock-trade", tags=["Mock Trading"])

class OrderRequest(BaseModel):
    ticker: str
    side: str
    qty: float
    price: float

@router.get("/portfolio")
async def get_mock_portfolio(
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: str = "default",
):
    # Get or create portfolio
    result = await db.execute(select(MockPortfolio).where(MockPortfolio.user_id == user_id))
    portfolio = result.scalars().first()

    if not portfolio:
        portfolio = MockPortfolio(user_id=user_id, cash_balance=100000.0)
        db.add(portfolio)
        await db.commit()
        await db.refresh(portfolio)

    pos_result = await db.execute(select(MockPosition).where(MockPosition.user_id == user_id))
    positions = pos_result.scalars().all()

    return {
        "cash_balance": portfolio.cash_balance,
        "positions": [
            {
                "ticker": p.ticker,
                "qty": p.qty,
                "average_entry_price": p.average_entry_price
            } for p in positions
        ]
    }

class FundRequest(BaseModel):
    amount: float

@router.post("/fund")
async def add_mock_funds(
    request: FundRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: str = "default",
):
    if request.amount <= 0:
        raise HTTPException(status_code=400, detail="Must add positive amount")

    result = await db.execute(select(MockPortfolio).where(MockPortfolio.user_id == user_id))
    portfolio = result.scalars().first()

    if not portfolio:
        portfolio = MockPortfolio(user_id=user_id, cash_balance=request.amount)
        db.add(portfolio)
    else:
        portfolio.cash_balance += request.amount

    await db.commit()
    await db.refresh(portfolio)

    return {"status": "success", "new_balance": portfolio.cash_balance}

@router.post("/order")
async def execute_mock_order(
    order: OrderRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: str = "default",
):
    if order.qty <= 0 or order.price <= 0:
        raise HTTPException(status_code=400, detail="Invalid quantity or price")

    result = await db.execute(select(MockPortfolio).where(MockPortfolio.user_id == user_id))
    portfolio = result.scalars().first()
    if not portfolio:
        portfolio = MockPortfolio(user_id=user_id, cash_balance=100000.0)
        db.add(portfolio)

    pos_result = await db.execute(select(MockPosition).where(MockPosition.user_id == user_id, MockPosition.ticker == order.ticker))
    position = pos_result.scalars().first()

    total_value = order.qty * order.price

    if order.side.upper() == "BUY":
        if portfolio.cash_balance < total_value:
            raise HTTPException(status_code=400, detail="Insufficient mock funds")

        portfolio.cash_balance -= total_value
        if position:
            total_cost = (position.qty * position.average_entry_price) + total_value
            position.qty += order.qty
            position.average_entry_price = total_cost / position.qty
        else:
            position = MockPosition(user_id=user_id, ticker=order.ticker, qty=order.qty, average_entry_price=order.price)
            db.add(position)

    elif order.side.upper() == "SELL":
        if not position or position.qty < order.qty:
            raise HTTPException(status_code=400, detail="Insufficient position quantity to sell")

        portfolio.cash_balance += total_value
        position.qty -= order.qty
        if position.qty == 0:
            await db.delete(position)

    else:
        raise HTTPException(status_code=400, detail="Side must be BUY or SELL")

    mock_trade = MockTrade(
        user_id=user_id,
        ticker=order.ticker,
        side=order.side.upper(),
        qty=order.qty,
        price=order.price,
        value=total_value
    )
    db.add(mock_trade)

    await db.commit()

    return {"status": "success", "message": f"{order.side.upper()} order processed for {order.qty} shares of {order.ticker}."}

# Note: We rely on Alpaca frontend integration for live quotes. If the frontend wants a backend proxy it can be added here.

@router.get("/quote/{ticker}")
async def get_quote(ticker: str):
    settings = get_settings()
    # Use Alpaca API (free for paper accounts)
    url = f"https://data.alpaca.markets/v2/stocks/{ticker}/quotes/latest"
    headers = {
        "APCA-API-KEY-ID": settings.alpaca_api_key,
        "APCA-API-SECRET-KEY": settings.alpaca_secret_key
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)

    if response.status_code != 200:
        # Fallback to simulated data or raise error
        return {"price": 150.0} # Fallback for now if rate limited / market close

    data = response.json()
    if "quote" in data and "ap" in data["quote"]:
        # ap = ask price, bp = bid price. Use ask price as execution price for buys
        return {"price": data["quote"]["ap"]}

    # fallback
    return {"price": 150.0}
