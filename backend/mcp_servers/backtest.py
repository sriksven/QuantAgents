"""
QuantAgents — Backtest MCP Server
Runs vectorbt strategy backtests and Monte Carlo simulations.
"""
from __future__ import annotations

import logging
from typing import Any

from mcp.server import FastMCP

logger = logging.getLogger(__name__)
mcp = FastMCP("backtest")


# ── Tool 1: Run Strategy Backtest ─────────────────────────────────────────────

@mcp.tool()
def run_backtest(
    ticker: str,
    strategy: str = "sma_crossover",
    start_date: str = "2022-01-01",
    end_date: str = "2024-12-31",
    initial_capital: float = 100_000.0,
    strategy_params: str = "",
) -> dict[str, Any]:
    """
    Run a vectorbt strategy backtest on historical price data.

    Args:
        ticker: Stock ticker symbol
        strategy: Strategy name. Options: sma_crossover, rsi_mean_reversion,
                  macd_momentum, bollinger_breakout, buy_and_hold
        start_date: Start date YYYY-MM-DD
        end_date: End date YYYY-MM-DD
        initial_capital: Starting capital in USD
        strategy_params: JSON string of strategy parameters (e.g. '{"fast": 20, "slow": 50}')

    Returns:
        Dict with performance metrics: total_return, CAGR, Sharpe, Sortino, max_drawdown,
        win_rate, profit_factor, total_trades, calmar_ratio.
    """
    import json
    import numpy as np

    try:
        import yfinance as yf
        import pandas as pd

        # Parse extra params
        params: dict = {}
        if strategy_params:
            try:
                params = json.loads(strategy_params)
            except json.JSONDecodeError:
                pass

        # Fetch price data
        df = yf.download(ticker.upper(), start=start_date, end=end_date, auto_adjust=True, progress=False)
        if df.empty:
            return {"error": f"No price data for {ticker} between {start_date} and {end_date}"}

        close = df["Close"].squeeze()
        trading_days = len(close)
        years = trading_days / 252

        # ── Generate signals per strategy ────────────────────
        if strategy == "sma_crossover":
            fast = params.get("fast", 20)
            slow = params.get("slow", 50)
            fast_ma = close.rolling(fast).mean()
            slow_ma = close.rolling(slow).mean()
            entries = (fast_ma > slow_ma) & (fast_ma.shift(1) <= slow_ma.shift(1))
            exits = (fast_ma < slow_ma) & (fast_ma.shift(1) >= slow_ma.shift(1))

        elif strategy == "rsi_mean_reversion":
            period = params.get("period", 14)
            oversold = params.get("oversold", 30)
            overbought = params.get("overbought", 70)
            delta = close.diff()
            gain = delta.clip(lower=0).rolling(period).mean()
            loss = (-delta.clip(upper=0)).rolling(period).mean()
            rs = gain / loss.replace(0, np.nan)
            rsi = 100 - (100 / (1 + rs))
            entries = rsi < oversold
            exits = rsi > overbought

        elif strategy == "macd_momentum":
            fast = params.get("fast", 12)
            slow = params.get("slow", 26)
            signal_p = params.get("signal", 9)
            ema_fast = close.ewm(span=fast).mean()
            ema_slow = close.ewm(span=slow).mean()
            macd = ema_fast - ema_slow
            signal_line = macd.ewm(span=signal_p).mean()
            entries = (macd > signal_line) & (macd.shift(1) <= signal_line.shift(1))
            exits = (macd < signal_line) & (macd.shift(1) >= signal_line.shift(1))

        elif strategy == "bollinger_breakout":
            period = params.get("period", 20)
            std_dev = params.get("std_dev", 2.0)
            mid = close.rolling(period).mean()
            std = close.rolling(period).std()
            upper = mid + std_dev * std
            lower = mid - std_dev * std
            entries = close < lower
            exits = close > upper

        else:  # buy_and_hold
            entries = pd.Series([True] + [False] * (len(close) - 1), index=close.index)
            exits = pd.Series([False] * (len(close) - 1) + [True], index=close.index)

        # ── Simulate trades manually ──────────────────────────
        in_position = False
        entry_price = 0.0
        trades: list[dict] = []
        position_returns: list[float] = []
        cash = initial_capital
        equity = initial_capital
        equity_curve: list[float] = [initial_capital]
        shares = 0.0

        for i, (date, price) in enumerate(close.items()):
            price = float(price)
            if np.isnan(price):
                equity_curve.append(equity)
                continue

            if not in_position and i < len(entries) and bool(entries.iloc[i]):
                shares = cash / price
                entry_price = price
                cash = 0.0
                in_position = True

            elif in_position and i < len(exits) and bool(exits.iloc[i]):
                exit_val = shares * price
                trade_return = (price - entry_price) / entry_price
                position_returns.append(trade_return)
                trades.append({
                    "entry": entry_price, "exit": price,
                    "return_pct": round(trade_return * 100, 2),
                    "pnl": round(exit_val - shares * entry_price, 2),
                })
                cash = exit_val
                shares = 0.0
                in_position = False

            equity = cash + (shares * price if in_position else 0)
            equity_curve.append(equity)

        # Close any open position at end
        if in_position:
            final_price = float(close.iloc[-1])
            exit_val = shares * final_price
            trade_return = (final_price - entry_price) / entry_price
            position_returns.append(trade_return)
            trades.append({"entry": entry_price, "exit": final_price,
                           "return_pct": round(trade_return * 100, 2), "pnl": round(exit_val - shares * entry_price, 2)})
            cash = exit_val

        final_equity = cash
        total_return = (final_equity - initial_capital) / initial_capital

        # ── Performance metrics ───────────────────────────────
        equity_arr = np.array(equity_curve[1:], dtype=float)
        daily_returns = np.diff(equity_arr) / equity_arr[:-1]
        daily_returns = daily_returns[~np.isnan(daily_returns)]

        cagr = (final_equity / initial_capital) ** (1 / max(years, 0.01)) - 1
        vol = float(np.std(daily_returns) * np.sqrt(252)) if len(daily_returns) > 0 else 0
        sharpe = float((np.mean(daily_returns) * 252 - 0.05) / vol) if vol > 0 else 0

        neg_rets = daily_returns[daily_returns < 0]
        downside_vol = float(np.std(neg_rets) * np.sqrt(252)) if len(neg_rets) > 0 else 0
        sortino = float((np.mean(daily_returns) * 252 - 0.05) / downside_vol) if downside_vol > 0 else 0

        # Max drawdown
        running_max = np.maximum.accumulate(equity_arr)
        drawdown = (equity_arr - running_max) / running_max
        max_dd = float(np.min(drawdown)) if len(drawdown) > 0 else 0

        calmar = float(cagr / abs(max_dd)) if max_dd != 0 else 0

        wins = [t for t in trades if t["return_pct"] > 0]
        losses = [t for t in trades if t["return_pct"] <= 0]
        win_rate = len(wins) / len(trades) if trades else 0

        gross_profit = sum(t["pnl"] for t in wins)
        gross_loss = abs(sum(t["pnl"] for t in losses))
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else float("inf")

        meets_min = (
            sharpe >= 1.0
            and max_dd >= -0.25
            and win_rate >= 0.45
            and len(trades) >= 10
        )

        return {
            "ticker": ticker.upper(),
            "strategy": strategy,
            "period": f"{start_date} to {end_date}",
            "initial_capital": initial_capital,
            "final_equity": round(final_equity, 2),
            "total_return_pct": round(total_return * 100, 2),
            "cagr_pct": round(cagr * 100, 2),
            "sharpe_ratio": round(sharpe, 3),
            "sortino_ratio": round(sortino, 3),
            "calmar_ratio": round(calmar, 3),
            "max_drawdown_pct": round(max_dd * 100, 2),
            "win_rate": round(win_rate, 3),
            "total_trades": len(trades),
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "profit_factor": round(profit_factor, 3),
            "meets_minimum_thresholds": meets_min,
            "rejection_reason": None if meets_min else (
                f"Sharpe={sharpe:.2f}<1.0" if sharpe < 1.0 else
                f"MaxDD={max_dd*100:.1f}%<-25%" if max_dd < -0.25 else
                f"WinRate={win_rate:.0%}<45%" if win_rate < 0.45 else
                f"Trades={len(trades)}<10"
            ),
        }
    except Exception as exc:
        logger.error("run_backtest(%s, %s) failed: %s", ticker, strategy, exc)
        return {"error": str(exc), "ticker": ticker, "strategy": strategy}


# ── Tool 2: Run Monte Carlo Simulation ───────────────────────────────────────

@mcp.tool()
def run_monte_carlo(
    ticker: str,
    strategy: str = "sma_crossover",
    n_simulations: int = 1000,
    start_date: str = "2022-01-01",
    end_date: str = "2024-12-31",
    initial_capital: float = 100_000.0,
) -> dict[str, Any]:
    """
    Run Monte Carlo simulation by bootstrapping daily trade returns.
    Estimates distribution of outcomes across N reshuffled return sequences.

    Args:
        ticker: Stock ticker
        strategy: Same strategy names as run_backtest
        n_simulations: Number of Monte Carlo paths (default 1000)
        start_date: Backtest start date
        end_date: Backtest end date
        initial_capital: Starting capital

    Returns:
        Dict with P5, P25, P50, P75, P95 outcomes and probability of ruin.
    """
    import numpy as np

    # First run base backtest to get trade returns
    base = run_backtest(ticker, strategy, start_date, end_date, initial_capital)
    if "error" in base:
        return base

    n_trades = base["total_trades"]
    win_rate = base["win_rate"]
    avg_win_pct = base["total_return_pct"] / max(n_trades, 1)  # rough proxy
    profit_factor = base["profit_factor"] if base["profit_factor"] != float("inf") else 3.0

    if n_trades < 5:
        return {"error": f"Too few trades ({n_trades}) for Monte Carlo simulation", "ticker": ticker}

    # Reconstruct approximate trade return distribution
    avg_win = abs(avg_win_pct) / 100 * (profit_factor / (1 + profit_factor))
    avg_loss = -avg_win / profit_factor
    trade_returns = (
        [avg_win] * int(win_rate * n_trades) +
        [avg_loss] * (n_trades - int(win_rate * n_trades))
    )
    trade_returns = np.array(trade_returns)

    # Monte Carlo: reshuffle returns N times
    final_equities = []
    ruin_count = 0  # equity drops below 50% of initial
    ruin_threshold = initial_capital * 0.5

    rng = np.random.default_rng(42)
    for _ in range(n_simulations):
        shuffled = rng.choice(trade_returns, size=len(trade_returns), replace=True)
        equity = initial_capital
        ruined = False
        for r in shuffled:
            equity *= (1 + r)
            if equity <= ruin_threshold:
                ruined = True
                break
        if ruined:
            ruin_count += 1
            final_equities.append(ruin_threshold)
        else:
            final_equities.append(equity)

    final_equities = np.array(final_equities)

    def to_return_pct(equity: float) -> float:
        return round((equity - initial_capital) / initial_capital * 100, 2)

    return {
        "ticker": ticker.upper(),
        "strategy": strategy,
        "n_simulations": n_simulations,
        "probability_of_ruin_pct": round(ruin_count / n_simulations * 100, 2),
        "percentile_outcomes": {
            "p5": {"equity": round(float(np.percentile(final_equities, 5)), 2),
                   "return_pct": to_return_pct(float(np.percentile(final_equities, 5)))},
            "p25": {"equity": round(float(np.percentile(final_equities, 25)), 2),
                    "return_pct": to_return_pct(float(np.percentile(final_equities, 25)))},
            "p50": {"equity": round(float(np.percentile(final_equities, 50)), 2),
                    "return_pct": to_return_pct(float(np.percentile(final_equities, 50)))},
            "p75": {"equity": round(float(np.percentile(final_equities, 75)), 2),
                    "return_pct": to_return_pct(float(np.percentile(final_equities, 75)))},
            "p95": {"equity": round(float(np.percentile(final_equities, 95)), 2),
                    "return_pct": to_return_pct(float(np.percentile(final_equities, 95)))},
        },
        "mean_equity": round(float(np.mean(final_equities)), 2),
        "std_equity": round(float(np.std(final_equities)), 2),
        "base_backtest_sharpe": base["sharpe_ratio"],
        "base_backtest_total_return_pct": base["total_return_pct"],
    }


if __name__ == "__main__":
    mcp.run()
