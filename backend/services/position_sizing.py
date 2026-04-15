"""
QuantAgents — Position Sizing Service
Half-Kelly criterion with volatility scaling, portfolio-level risk controls,
and paper/live trading gates.
"""

from __future__ import annotations

import logging
import math
from typing import Any

logger = logging.getLogger(__name__)


def compute_half_kelly(
    win_rate: float,
    avg_win_pct: float,
    avg_loss_pct: float,
    confidence: float = 1.0,
) -> float:
    """
    Compute the half-Kelly fraction for position sizing.

    Kelly formula: f = (p * b - q) / b
    where:
      p = win_rate
      q = 1 - win_rate
      b = avg_win / avg_loss (reward-risk ratio)

    Half-Kelly = f / 2  (conservative variant)

    Args:
        win_rate: Historical win rate [0, 1]
        avg_win_pct: Average winning trade return %
        avg_loss_pct: Average losing trade return % (positive number, e.g. 3.5 for -3.5%)
        confidence: Agent confidence [0,1] — further scales fraction

    Returns:
        Recommended portfolio fraction [0, 0.20] capped at 20%
    """
    if avg_loss_pct <= 0 or not (0 < win_rate < 1):
        return 0.0

    b = avg_win_pct / avg_loss_pct  # reward-risk ratio
    q = 1 - win_rate
    kelly = (win_rate * b - q) / b
    half_kelly = kelly / 2 * confidence

    # Hard caps
    return max(0.0, min(half_kelly, 0.20))


def compute_position_size(
    ticker: str,
    action: str,
    recommendation_confidence: float,
    portfolio_value: float,
    current_price: float,
    win_rate: float = 0.55,
    avg_win_pct: float = 5.0,
    avg_loss_pct: float = 3.0,
    volatility_20d: float | None = None,
    target_volatility: float = 0.15,
    max_position_pct: float = 0.05,
    existing_position_value: float = 0.0,
) -> dict[str, Any]:
    """
    Full position sizing computation with volatility scaling.

    Args:
        ticker: Stock ticker
        action: "BUY" or "SELL"
        recommendation_confidence: Agent confidence [0, 1]
        portfolio_value: Total portfolio value in USD
        current_price: Current stock price
        win_rate: Historical win rate from trade journal
        avg_win_pct: Avg winning trade %
        avg_loss_pct: Avg losing trade % (absolute)
        volatility_20d: 20-day annualized volatility (None = skip vol scaling)
        target_volatility: Target portfolio contribution volatility (15% annualized)
        max_position_pct: Hard cap on single position (default 5%)
        existing_position_value: Already-held dollar value in this position

    Returns:
        Dict with recommended_shares, notional, pct_of_portfolio, stop_loss_price,
        take_profit_price, reasoning.
    """
    if action.upper() == "HOLD":
        return {
            "ticker": ticker.upper(),
            "action": "HOLD",
            "recommended_shares": 0,
            "notional": 0.0,
            "pct_of_portfolio": 0.0,
            "reasoning": "HOLD signal — no position change recommended",
        }

    # 1. Half-Kelly base fraction
    kelly_frac = compute_half_kelly(win_rate, avg_win_pct, avg_loss_pct, recommendation_confidence)

    # 2. Volatility scaling: scale down if vol is high
    vol_scalar = 1.0
    if volatility_20d and volatility_20d > 0:
        vol_scalar = min(1.0, target_volatility / volatility_20d)
        kelly_frac *= vol_scalar

    # 3. Apply max position cap
    kelly_frac = min(kelly_frac, max_position_pct)

    # 4. Subtract existing exposure
    existing_pct = existing_position_value / portfolio_value if portfolio_value > 0 else 0
    incremental_frac = max(0.0, kelly_frac - existing_pct)

    # 5. Convert to dollar notional and shares
    notional = portfolio_value * incremental_frac
    shares = math.floor(notional / current_price) if current_price > 0 else 0
    actual_notional = shares * current_price

    # 6. Stop loss and take profit (fixed ratio based on avg win/loss)
    stop_loss_price = round(current_price * (1 - avg_loss_pct / 100), 2)
    take_profit_price = round(current_price * (1 + avg_win_pct / 100), 2)

    # Risk sanity checks
    warnings: list[str] = []
    if actual_notional < 100:
        warnings.append("Notional < $100 — consider skipping this trade")
    if recommendation_confidence < 0.5:
        warnings.append(f"Low confidence ({recommendation_confidence:.0%}) — sizing reduced")
    if vol_scalar < 0.5:
        warnings.append(f"High volatility causing {vol_scalar:.0%} size reduction")

    return {
        "ticker": ticker.upper(),
        "action": action.upper(),
        "recommended_shares": shares,
        "notional": round(actual_notional, 2),
        "pct_of_portfolio": round(actual_notional / portfolio_value * 100, 2)
        if portfolio_value > 0
        else 0,
        "kelly_fraction": round(kelly_frac, 4),
        "vol_scalar": round(vol_scalar, 3),
        "stop_loss_price": stop_loss_price,
        "take_profit_price": take_profit_price,
        "risk_reward_ratio": round(avg_win_pct / avg_loss_pct, 2),
        "warnings": warnings,
        "reasoning": (
            f"Half-Kelly={kelly_frac:.1%} × vol_scalar={vol_scalar:.2f} × "
            f"confidence={recommendation_confidence:.0%} → "
            f"{shares} shares @ ${current_price:.2f} = ${actual_notional:,.0f} "
            f"({actual_notional / portfolio_value * 100:.1f}% of portfolio)"
        ),
    }
