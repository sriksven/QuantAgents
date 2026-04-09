"""
QuantAgents — Options Strategy Selection Service
IV-aware strategy selection based on direction, IV rank, and time horizon.
Pure Python — no external dependencies beyond the standard library.
"""
from __future__ import annotations

import math
from typing import Any


# ── Greeks approximation (Black-Scholes) ─────────────────────────────────────

def black_scholes_call(S: float, K: float, T: float, r: float, sigma: float) -> dict[str, float]:
    """
    Black-Scholes call option price and Greeks.

    Args:
        S: Current stock price
        K: Strike price
        T: Time to expiry in years
        r: Risk-free rate (e.g. 0.05 for 5%)
        sigma: Implied volatility (annualized, e.g. 0.25)

    Returns:
        Dict with price, delta, gamma, theta (daily), vega (per 1% IV move)
    """
    if T <= 0 or sigma <= 0 or S <= 0 or K <= 0:
        return {"price": 0.0, "delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0}

    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)

    def N(x: float) -> float:
        """Standard normal CDF approximation."""
        return 0.5 * (1 + math.erf(x / math.sqrt(2)))

    def n(x: float) -> float:
        """Standard normal PDF."""
        return math.exp(-0.5 * x ** 2) / math.sqrt(2 * math.pi)

    price = S * N(d1) - K * math.exp(-r * T) * N(d2)
    delta = N(d1)
    gamma = n(d1) / (S * sigma * math.sqrt(T))
    theta = (-(S * n(d1) * sigma) / (2 * math.sqrt(T)) - r * K * math.exp(-r * T) * N(d2)) / 365
    vega = S * n(d1) * math.sqrt(T) / 100  # per 1% IV move

    return {
        "price": round(price, 4),
        "delta": round(delta, 4),
        "gamma": round(gamma, 6),
        "theta": round(theta, 4),
        "vega": round(vega, 4),
    }


def black_scholes_put(S: float, K: float, T: float, r: float, sigma: float) -> dict[str, float]:
    """Black-Scholes put option price and Greeks via put-call parity."""
    call = black_scholes_call(S, K, T, r, sigma)
    put_price = call["price"] - S + K * math.exp(-r * T)
    put_delta = call["delta"] - 1.0
    return {
        "price": round(put_price, 4),
        "delta": round(put_delta, 4),
        "gamma": call["gamma"],
        "theta": call["theta"],
        "vega": call["vega"],
    }


# ── Strategy Selector ─────────────────────────────────────────────────────────

def select_options_strategy(
    direction: str,
    iv_rank: float,
    days_to_expiry: int = 45,
    current_price: float | None = None,
    stop_loss: float | None = None,
    take_profit: float | None = None,
) -> dict[str, Any]:
    """
    Select the optimal options strategy given market direction and IV environment.

    Decision matrix:
    ┌──────────────┬──────────────────┬──────────────────────────────────┐
    │ Direction    │ IV Rank          │ Preferred Strategy               │
    ├──────────────┼──────────────────┼──────────────────────────────────┤
    │ BUY          │ Low  (<30%)      │ Long call (buy options cheap)    │
    │ BUY          │ High (>70%)      │ Bull put spread (sell premium)   │
    │ BUY          │ Moderate (30-70%)│ Bull call spread (defined risk)  │
    │ SELL/BEARISH │ Low  (<30%)      │ Long put (buy options cheap)     │
    │ SELL/BEARISH │ High (>70%)      │ Bear call spread (sell premium)  │
    │ SELL/BEARISH │ Moderate (30-70%)│ Bear put spread (defined risk)   │
    │ NEUTRAL/HOLD │ High (>70%)      │ Iron condor (max premium)        │
    │ NEUTRAL/HOLD │ Moderate (30-70%)│ Covered call (if long stock)     │
    │ NEUTRAL/HOLD │ Low  (<30%)      │ No options — wait for IV to rise  │
    └──────────────┴──────────────────┴──────────────────────────────────┘

    Args:
        direction: "BUY", "SELL", or "HOLD"
        iv_rank: IV rank [0-100] (percentile of current IV vs. 52-week range)
        days_to_expiry: Target DTE (default 45)
        current_price: Current stock price (for strike estimation)
        stop_loss: Strategy stop loss (for defining spread width)
        take_profit: Strategy take profit (for defining spread width)

    Returns:
        Dict with strategy_name, rationale, risk_reward_profile, suggested_legs, and ideal_dte
    """
    direction = direction.upper()
    iv_env = "low" if iv_rank < 30 else "high" if iv_rank > 70 else "moderate"
    S = current_price or 100.0
    atm = round(S, 0)

    strategies: dict[str, Any] = {}

    if direction == "BUY":
        if iv_env == "low":
            strategies = {
                "strategy_name": "long_call",
                "rationale": (
                    f"IV rank is low ({iv_rank:.0f}%) — options are cheap. "
                    "Long call maximizes directional leverage while buying premium at a discount."
                ),
                "ideal_dte": max(30, days_to_expiry),
                "risk_profile": "Limited risk (premium paid), unlimited upside",
                "suggested_legs": [
                    {"action": "buy", "option_type": "call", "strike": atm, "contracts": 1}
                ],
                "max_loss": "Premium paid",
                "max_gain": "Theoretically unlimited",
                "breakeven_offset_pct": 2.5,
            }
        elif iv_env == "high":
            width = round(S * 0.05, 0)  # 5% spread width
            strategies = {
                "strategy_name": "bull_put_spread",
                "rationale": (
                    f"IV rank is high ({iv_rank:.0f}%) — sell premium. "
                    "Bull put spread collects rich credit while defining max loss."
                ),
                "ideal_dte": min(45, days_to_expiry),
                "risk_profile": "Limited risk/reward, positive theta",
                "suggested_legs": [
                    {"action": "sell", "option_type": "put", "strike": round(S * 0.97, 0), "contracts": 1},
                    {"action": "buy",  "option_type": "put", "strike": round(S * 0.97, 0) - width, "contracts": 1},
                ],
                "max_loss": f"Spread width minus credit received (~${width:.0f} per share)",
                "max_gain": "Credit received",
                "breakeven_offset_pct": -3.0,
            }
        else:
            strategies = {
                "strategy_name": "bull_call_spread",
                "rationale": (
                    f"IV rank is moderate ({iv_rank:.0f}%). "
                    "Bull call spread reduces cost vs. long call while keeping directional exposure."
                ),
                "ideal_dte": max(21, days_to_expiry),
                "risk_profile": "Limited risk, limited reward (defined)",
                "suggested_legs": [
                    {"action": "buy",  "option_type": "call", "strike": atm, "contracts": 1},
                    {"action": "sell", "option_type": "call", "strike": round(S * 1.05, 0), "contracts": 1},
                ],
                "max_loss": "Net debit paid",
                "max_gain": "Spread width minus net debit",
                "breakeven_offset_pct": 2.0,
            }

    elif direction in ("SELL", "BEARISH"):
        if iv_env == "low":
            strategies = {
                "strategy_name": "long_put",
                "rationale": (
                    f"IV rank is low ({iv_rank:.0f}%) — options are cheap. "
                    "Long put delivers directional downside exposure at a discounted premium."
                ),
                "ideal_dte": max(30, days_to_expiry),
                "risk_profile": "Limited risk (premium paid), large downside gain",
                "suggested_legs": [
                    {"action": "buy", "option_type": "put", "strike": atm, "contracts": 1}
                ],
                "max_loss": "Premium paid",
                "max_gain": "Strike price minus premium (as stock → 0)",
                "breakeven_offset_pct": -2.5,
            }
        elif iv_env == "high":
            width = round(S * 0.05, 0)
            strategies = {
                "strategy_name": "bear_call_spread",
                "rationale": (
                    f"IV rank is high ({iv_rank:.0f}%) — sell premium. "
                    "Bear call spread captures rich call premium with defined upside risk."
                ),
                "ideal_dte": min(45, days_to_expiry),
                "risk_profile": "Limited risk/reward, positive theta",
                "suggested_legs": [
                    {"action": "sell", "option_type": "call", "strike": round(S * 1.03, 0), "contracts": 1},
                    {"action": "buy",  "option_type": "call", "strike": round(S * 1.03, 0) + width, "contracts": 1},
                ],
                "max_loss": "Spread width minus credit",
                "max_gain": "Credit received",
                "breakeven_offset_pct": 3.0,
            }
        else:
            strategies = {
                "strategy_name": "bear_put_spread",
                "rationale": (
                    f"IV rank is moderate ({iv_rank:.0f}%). "
                    "Bear put spread reduces put cost while defining max loss."
                ),
                "ideal_dte": max(21, days_to_expiry),
                "risk_profile": "Limited risk, limited reward (defined)",
                "suggested_legs": [
                    {"action": "buy",  "option_type": "put", "strike": atm, "contracts": 1},
                    {"action": "sell", "option_type": "put", "strike": round(S * 0.95, 0), "contracts": 1},
                ],
                "max_loss": "Net debit paid",
                "max_gain": "Spread width minus net debit",
                "breakeven_offset_pct": -2.0,
            }

    else:  # HOLD / NEUTRAL
        if iv_env == "high":
            width = round(S * 0.05, 0)
            strategies = {
                "strategy_name": "iron_condor",
                "rationale": (
                    f"IV rank is high ({iv_rank:.0f}%) and stock direction is neutral. "
                    "Iron condor collects maximum premium by selling both sides."
                ),
                "ideal_dte": min(45, days_to_expiry),
                "risk_profile": "Limited risk/reward, profits from time decay and IV crush",
                "suggested_legs": [
                    {"action": "sell", "option_type": "put",  "strike": round(S * 0.95, 0), "contracts": 1},
                    {"action": "buy",  "option_type": "put",  "strike": round(S * 0.95, 0) - width, "contracts": 1},
                    {"action": "sell", "option_type": "call", "strike": round(S * 1.05, 0), "contracts": 1},
                    {"action": "buy",  "option_type": "call", "strike": round(S * 1.05, 0) + width, "contracts": 1},
                ],
                "max_loss": "Spread width minus total credit (on either side)",
                "max_gain": "Total credit received",
                "breakeven_offset_pct": 5.0,
            }
        elif iv_env == "moderate":
            strategies = {
                "strategy_name": "covered_call",
                "rationale": (
                    f"IV rank is moderate ({iv_rank:.0f}%) and direction is neutral. "
                    "Covered call generates income on an existing long stock position."
                ),
                "ideal_dte": min(30, days_to_expiry),
                "risk_profile": "Reduces cost basis; caps upside; downside not hedged",
                "suggested_legs": [
                    {"action": "sell", "option_type": "call",
                     "strike": round(S * 1.05, 0), "contracts": 1}
                ],
                "max_loss": "Full stock loss minus premium received",
                "max_gain": "Premium + stock gain up to strike",
                "breakeven_offset_pct": -5.0,
            }
        else:
            strategies = {
                "strategy_name": "no_options_trade",
                "rationale": (
                    f"IV rank is low ({iv_rank:.0f}%) and direction is neutral. "
                    "No attractive options setup — wait for IV to rise or stock to move."
                ),
                "ideal_dte": None,
                "suggested_legs": [],
                "max_loss": "N/A",
                "max_gain": "N/A",
                "breakeven_offset_pct": None,
            }

    # Add BS pricing estimates if we have a price
    if current_price and strategies.get("suggested_legs"):
        T = (strategies.get("ideal_dte") or 45) / 365
        r = 0.05
        sigma = iv_rank / 100 * 0.40 + 0.10  # rough IV estimate from rank
        priced_legs = []
        net_debit = 0.0
        for leg in strategies["suggested_legs"]:
            K = float(leg.get("strike", S))
            opt_type = leg.get("option_type", "call")
            bs = black_scholes_call(S, K, T, r, sigma) if opt_type == "call" else black_scholes_put(S, K, T, r, sigma)
            multiplier = -1 if leg["action"] == "sell" else 1
            net_debit += multiplier * bs["price"]
            priced_legs.append({
                **leg,
                "estimated_price": bs["price"],
                "delta": bs["delta"],
                "theta": bs["theta"],
                "vega": bs["vega"],
            })
        strategies["priced_legs"] = priced_legs
        strategies["estimated_net_debit_per_share"] = round(net_debit, 4)
        strategies["estimated_net_debit_total"] = round(net_debit * 100, 2)  # 1 contract = 100 shares

    return {
        "direction": direction,
        "iv_rank": iv_rank,
        "iv_environment": iv_env,
        "days_to_expiry": days_to_expiry,
        **strategies,
    }


def compute_options_position_size(
    strategy_name: str,
    net_debit_per_share: float,
    portfolio_value: float,
    confidence: float,
    max_options_allocation_pct: float = 0.03,
) -> dict[str, Any]:
    """
    Compute number of contracts for an options position.

    Args:
        strategy_name: Strategy name (for context)
        net_debit_per_share: Net debit per share (premium paid / received)
        portfolio_value: Total portfolio value
        confidence: Agent confidence [0, 1]
        max_options_allocation_pct: Max % of portfolio for options premium (default 3%)

    Returns:
        Dict with contracts, total_premium, pct_of_portfolio.
    """
    if net_debit_per_share <= 0 or strategy_name == "no_options_trade":
        return {
            "contracts": 0,
            "total_premium": 0.0,
            "pct_of_portfolio": 0.0,
            "reasoning": "No debit or no-trade strategy",
        }

    # Max premium budget (confidence-scaled)
    max_premium = portfolio_value * max_options_allocation_pct * confidence
    # Each contract = 100 shares
    cost_per_contract = net_debit_per_share * 100
    contracts = max(0, int(max_premium / cost_per_contract)) if cost_per_contract > 0 else 0
    actual_premium = contracts * cost_per_contract

    return {
        "contracts": contracts,
        "total_premium": round(actual_premium, 2),
        "cost_per_contract": round(cost_per_contract, 2),
        "pct_of_portfolio": round(actual_premium / portfolio_value * 100, 2) if portfolio_value > 0 else 0,
        "reasoning": (
            f"{contracts} contract(s) × ${cost_per_contract:.2f}/contract = "
            f"${actual_premium:.2f} ({actual_premium/portfolio_value*100:.1f}% of portfolio)"
        ),
    }
