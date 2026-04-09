"""
QuantAgents — Options MCP Server
Tools for options chain analysis, strategy pricing, and execution via Alpaca.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from mcp.server import FastMCP

logger = logging.getLogger(__name__)
mcp = FastMCP("options")


# ── Tool 1: Analyze IV Environment ────────────────────────────────────────────

@mcp.tool()
def analyze_iv_environment(ticker: str) -> dict[str, Any]:
    """
    Analyze the implied volatility environment for a stock.
    Returns IV rank, HV comparison, and term structure.

    Args:
        ticker: Stock ticker symbol

    Returns:
        Dict with iv_rank, hv_20d, hv_iv_ratio, term_structure, and trading_implications
    """
    try:
        import yfinance as yf
        import numpy as np

        tk = yf.Ticker(ticker.upper())

        # Get historical prices for HV computation
        hist = tk.history(period="1y")
        if hist.empty:
            return {"error": f"No historical data for {ticker}"}

        close = hist["Close"]
        daily_returns = close.pct_change().dropna()

        # Historical volatility: 20-day and 60-day rolling
        hv_20 = float(daily_returns.tail(20).std() * (252 ** 0.5))
        hv_60 = float(daily_returns.tail(60).std() * (252 ** 0.5))
        hv_252 = float(daily_returns.std() * (252 ** 0.5))

        # Rolling 20-day HV over past year for IV rank proxy
        rolling_hv = daily_returns.rolling(20).std() * (252 ** 0.5)
        hv_52w_low = float(rolling_hv.min())
        hv_52w_high = float(rolling_hv.max())

        # IV from options chain (first available expiry)
        info = tk.info
        iv_estimate = float(info.get("impliedVolatility") or 0)
        if not iv_estimate:
            # Estimate from ATM option if no direct IV
            try:
                expiries = tk.options
                if expiries:
                    chain = tk.option_chain(expiries[0])
                    atm_calls = chain.calls
                    current_price = float(close.iloc[-1])
                    atm_call = atm_calls.iloc[(atm_calls["strike"] - current_price).abs().argsort()[:1]]
                    iv_estimate = float(atm_call["impliedVolatility"].values[0]) if not atm_call.empty else hv_20
            except Exception:
                iv_estimate = hv_20

        # IV Rank = (current IV - 52w low) / (52w high - 52w low)
        iv_rank = max(0.0, min(100.0, (iv_estimate - hv_52w_low) / max(hv_52w_high - hv_52w_low, 0.001) * 100))
        hv_iv_ratio = round(hv_20 / iv_estimate, 3) if iv_estimate > 0 else None

        # IV environment classification
        iv_env = "low" if iv_rank < 30 else "high" if iv_rank > 70 else "moderate"

        # Term structure: short vs long end
        term_structure = "flat"
        try:
            expiries = tk.options
            if len(expiries) >= 2:
                chain0 = tk.option_chain(expiries[0])
                chain1 = tk.option_chain(expiries[-1] if len(expiries) > 3 else expiries[1])
                iv0 = float(chain0.calls["impliedVolatility"].median() or 0)
                iv1 = float(chain1.calls["impliedVolatility"].median() or 0)
                term_structure = "backwardated" if iv0 > iv1 * 1.05 else "contango" if iv1 > iv0 * 1.05 else "flat"
        except Exception:
            pass

        implications = {
            "low": "IV is cheap — buy options (long calls/puts) to maximize leverage",
            "moderate": "Balanced — use spreads to reduce cost",
            "high": "IV is expensive — sell premium (spreads, iron condor, covered calls)",
        }

        return {
            "ticker": ticker.upper(),
            "current_iv": round(iv_estimate, 4),
            "hv_20d": round(hv_20, 4),
            "hv_60d": round(hv_60, 4),
            "hv_252d": round(hv_252, 4),
            "hv_iv_ratio": hv_iv_ratio,
            "iv_rank": round(iv_rank, 1),
            "iv_52w_low_proxy": round(hv_52w_low, 4),
            "iv_52w_high_proxy": round(hv_52w_high, 4),
            "iv_environment": iv_env,
            "term_structure": term_structure,
            "trading_implication": implications[iv_env],
        }
    except Exception as exc:
        logger.error("analyze_iv_environment(%s) failed: %s", ticker, exc)
        return {"error": str(exc), "ticker": ticker}


# ── Tool 2: Select Options Strategy ──────────────────────────────────────────

@mcp.tool()
def select_strategy(
    ticker: str,
    direction: str,
    iv_rank: float,
    days_to_expiry: int = 45,
    current_price: float | None = None,
) -> dict[str, Any]:
    """
    Select the optimal options strategy given direction and IV environment.
    Uses the IV × direction decision matrix.

    Args:
        ticker: Stock ticker
        direction: "BUY", "SELL", or "HOLD"
        iv_rank: IV rank [0-100]
        days_to_expiry: Target DTE (default 45)
        current_price: Current stock price for strike calculations

    Returns:
        Dict with strategy_name, suggested_legs, pricing estimates, and rationale.
    """
    from services.options_strategy import select_options_strategy
    result = select_options_strategy(direction, iv_rank, days_to_expiry, current_price)
    return {"ticker": ticker.upper(), **result}


# ── Tool 3: Price Options Strategy ───────────────────────────────────────────

@mcp.tool()
def price_strategy(
    ticker: str,
    strategy_name: str,
    legs: str,
    days_to_expiry: int = 45,
) -> dict[str, Any]:
    """
    Price an options strategy using live chain data from yfinance.

    Args:
        ticker: Stock ticker
        strategy_name: Human-readable strategy name
        legs: JSON string of legs: [{"action":"buy","option_type":"call","strike":180}, ...]
        days_to_expiry: Target DTE for expiry selection

    Returns:
        Dict with per-leg prices, net debit/credit, break-even, and Greeks summary.
    """
    import json
    import yfinance as yf
    from datetime import datetime, timedelta

    try:
        leg_list = json.loads(legs)
    except json.JSONDecodeError as exc:
        return {"error": f"Invalid legs JSON: {exc}"}

    try:
        tk = yf.Ticker(ticker.upper())
        target_date = datetime.utcnow() + timedelta(days=days_to_expiry)
        expiries = tk.options
        if not expiries:
            return {"error": f"No options data for {ticker}"}

        # Pick closest expiry to target DTE
        best_expiry = min(expiries, key=lambda e: abs((datetime.strptime(e, "%Y-%m-%d") - target_date).days))
        chain = tk.option_chain(best_expiry)
        info = tk.info
        current_price = float(info.get("regularMarketPrice") or info.get("currentPrice") or 0)

        priced_legs = []
        net_debit = 0.0
        total_delta = 0.0
        total_theta = 0.0
        total_vega = 0.0

        for leg in leg_list:
            strike = float(leg.get("strike", current_price))
            opt_type = str(leg.get("option_type", "call")).lower()
            action = str(leg.get("action", "buy")).lower()

            df = chain.calls if opt_type == "call" else chain.puts
            row = df.iloc[(df["strike"] - strike).abs().argsort()[:1]]

            if not row.empty:
                r = row.iloc[0]
                mid = round((float(r["bid"]) + float(r["ask"])) / 2, 4)
                iv = float(r.get("impliedVolatility", 0.25) or 0.25)
                delta = float(r.get("delta", 0) or (0.5 if opt_type == "call" else -0.5))
                theta = float(r.get("theta", 0) or -0.01)
                vega = float(r.get("vega", 0) or 0.1)

                multiplier = -1 if action == "sell" else 1
                net_debit += multiplier * mid
                total_delta += multiplier * delta
                total_theta += multiplier * theta
                total_vega += multiplier * vega

                priced_legs.append({
                    "action": action,
                    "option_type": opt_type,
                    "strike": float(r["strike"]),
                    "expiry": best_expiry,
                    "bid": float(r["bid"]),
                    "ask": float(r["ask"]),
                    "mid": mid,
                    "iv": round(iv, 4),
                    "delta": round(delta, 4),
                    "theta": round(theta, 4),
                    "vega": round(vega, 4),
                    "oi": int(r.get("openInterest", 0) or 0),
                })
            else:
                priced_legs.append({**leg, "error": f"No matching option at strike {strike}"})

        # Break-even estimates
        if strategy_name in ("long_call", "bull_call_spread"):
            breakeven = current_price + net_debit
        elif strategy_name in ("long_put", "bear_put_spread"):
            breakeven = current_price - abs(net_debit)
        elif net_debit < 0:  # credit strategies
            breakeven = current_price + abs(net_debit)
        else:
            breakeven = current_price

        return {
            "ticker": ticker.upper(),
            "strategy_name": strategy_name,
            "expiry": best_expiry,
            "current_price": current_price,
            "legs": priced_legs,
            "net_debit_per_share": round(net_debit, 4),
            "net_debit_per_contract": round(net_debit * 100, 2),
            "breakeven": round(breakeven, 2),
            "breakeven_move_pct": round((breakeven - current_price) / current_price * 100, 2) if current_price else 0,
            "portfolio_greeks": {
                "delta": round(total_delta, 4),
                "theta_daily": round(total_theta, 4),
                "vega_per_1pct": round(total_vega, 4),
            },
        }
    except Exception as exc:
        logger.error("price_strategy(%s, %s) failed: %s", ticker, strategy_name, exc)
        return {"error": str(exc), "ticker": ticker}


# ── Tool 4: Backtest Options Strategy ─────────────────────────────────────────

@mcp.tool()
def backtest_options_strategy(
    ticker: str,
    strategy_name: str = "bull_call_spread",
    direction: str = "BUY",
    start_date: str = "2023-01-01",
    end_date: str = "2024-12-31",
    days_to_expiry: int = 45,
    iv_rank_threshold: float = 50.0,
) -> dict[str, Any]:
    """
    Backtest a monthly options strategy on historical data.
    Enters a new position every month and closes 14 days before expiry.

    Args:
        ticker: Stock ticker
        strategy_name: Options strategy to backtest
        direction: "BUY", "SELL", or "HOLD"
        start_date: Backtest start date (YYYY-MM-DD)
        end_date: Backtest end date (YYYY-MM-DD)
        days_to_expiry: Target DTE at entry
        iv_rank_threshold: Only enter if IV rank is above this (for premium selling)

    Returns:
        Dict with win_rate, avg_return_pct, max_loss, total_trades, annualized_return.
    """
    import yfinance as yf
    import numpy as np
    from datetime import datetime, timedelta
    from services.options_strategy import select_options_strategy, black_scholes_call, black_scholes_put

    try:
        df = yf.download(ticker.upper(), start=start_date, end=end_date,
                         auto_adjust=True, progress=False)
        if df.empty:
            return {"error": f"No price data for {ticker}"}

        close = df["Close"].squeeze()

        # Simulate monthly option entries
        trades = []
        entry_dates = []
        idx = 0
        n = len(close)
        entry_interval = 21  # monthly

        daily_returns = close.pct_change().dropna()

        while idx < n - days_to_expiry:
            entry_date = close.index[idx]
            entry_price = float(close.iloc[idx])
            exit_idx = min(idx + days_to_expiry - 14, n - 1)
            exit_price = float(close.iloc[exit_idx])

            # Compute historical vol at entry as IV proxy
            hist_window = daily_returns.iloc[max(0, idx-60):idx]
            iv = float(hist_window.std() * (252 ** 0.5)) if len(hist_window) > 10 else 0.25

            # Compute rolling HV range for IV rank
            rolling = daily_returns.rolling(20).std() * (252 ** 0.5)
            roll_slice = rolling.iloc[max(0, idx-252):idx]
            hv_low = float(roll_slice.min()) if len(roll_slice) > 20 else iv * 0.5
            hv_high = float(roll_slice.max()) if len(roll_slice) > 20 else iv * 1.5
            iv_rank = max(0, min(100, (iv - hv_low) / max(hv_high - hv_low, 0.001) * 100))

            # Select appropriate strategy
            strategy = select_options_strategy(direction, iv_rank, days_to_expiry, entry_price)

            # Simplified P&L: use BS pricing at entry and exit
            T_entry = days_to_expiry / 365
            T_exit = 14 / 365
            r = 0.05

            def price_leg(leg, S, T):
                K = float(leg.get("strike", S))
                opt_fn = black_scholes_call if leg.get("option_type") == "call" else black_scholes_put
                return opt_fn(S, K, T, r, iv).get("price", 0.0)

            legs = strategy.get("suggested_legs", [])
            if not legs:
                idx += entry_interval
                continue

            entry_val = sum(
                (-1 if leg["action"] == "sell" else 1) * price_leg(leg, entry_price, T_entry)
                for leg in legs
            )
            exit_val = sum(
                (-1 if leg["action"] == "sell" else 1) * price_leg(leg, exit_price, T_exit)
                for leg in legs
            )

            # For credit strategies: profit when exit_val > entry_val (net credit collected)
            pnl_per_share = exit_val - entry_val
            pnl_pct = pnl_per_share / abs(entry_val) * 100 if entry_val != 0 else 0

            trades.append({
                "entry_date": str(entry_date)[:10],
                "entry_price": round(entry_price, 2),
                "exit_price": round(exit_price, 2),
                "iv_rank": round(iv_rank, 1),
                "strategy": strategy["strategy_name"],
                "pnl_per_share": round(pnl_per_share, 4),
                "pnl_pct": round(pnl_pct, 2),
            })

            idx += entry_interval

        if not trades:
            return {"error": "No trades generated — check date range and parameters"}

        pnls = [t["pnl_pct"] for t in trades]
        wins = [p for p in pnls if p > 0]
        losses = [p for p in pnls if p <= 0]
        years = (datetime.strptime(end_date, "%Y-%m-%d") - datetime.strptime(start_date, "%Y-%m-%d")).days / 365

        return {
            "ticker": ticker.upper(),
            "strategy": strategy_name,
            "period": f"{start_date} to {end_date}",
            "total_trades": len(trades),
            "win_rate": round(len(wins) / len(trades), 3),
            "avg_return_pct": round(float(np.mean(pnls)), 2),
            "median_return_pct": round(float(np.median(pnls)), 2),
            "max_win_pct": round(max(pnls), 2),
            "max_loss_pct": round(min(pnls), 2),
            "profit_factor": round(sum(wins) / abs(sum(losses)), 3) if losses else None,
            "annualized_return_pct": round(float(np.mean(pnls)) * (12 / max(years, 0.1)), 2),
            "trades_sample": trades[:5],
        }
    except Exception as exc:
        logger.error("backtest_options_strategy failed: %s", exc)
        return {"error": str(exc), "ticker": ticker}


if __name__ == "__main__":
    mcp.run()
