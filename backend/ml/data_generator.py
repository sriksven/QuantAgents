"""
QuantAgents — Training Data Generator
Generates synthetic + historically-grounded training samples for 3 ML models:
  1. Confidence Calibrator  — predicts true accuracy from agent-reported confidence
  2. Reward Predictor       — predicts 30/60/90-day RL reward given analysis features
  3. Options Pricer         — predicts IV rank given market microstructure features

Output: Parquet files in data/training/{model_name}/
"""
from __future__ import annotations

import logging
import os
import random
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

TICKERS = [
    "AAPL", "MSFT", "NVDA", "GOOG", "AMZN", "TSLA", "META", "JPM",
    "GS", "BAC", "XOM", "CVX", "JNJ", "PFE", "LLY", "V", "MA",
    "UNH", "HD", "WMT", "SPY", "QQQ", "IWM", "GLD", "TLT",
]

OUTPUT_DIR = Path("data/training")

rng = np.random.default_rng(42)


# ── Feature helpers ────────────────────────────────────────────────────────────

def _realistic_confidence() -> float:
    """Agent-reported confidence: slightly over-confident (mean ~0.68)."""
    return float(np.clip(rng.beta(5, 2.5), 0.3, 0.95))


def _market_regime() -> str:
    """Randomly sample a market regime."""
    return random.choice(["bull", "bear", "sideways", "volatile", "recovery"])


def _debate_rounds() -> int:
    return random.choice([0, 1, 1, 2, 2, 2, 3])


def _market_features() -> dict[str, Any]:
    """Simulate a vector of market microstructure features."""
    hv_20 = float(rng.uniform(0.10, 0.55))
    hv_60 = hv_20 * rng.uniform(0.85, 1.15)
    iv = hv_20 * rng.uniform(0.8, 2.0)
    iv_rank = float(np.clip((iv - 0.10) / 0.50 * 100, 0, 100))

    return {
        "hv_20d": round(hv_20, 4),
        "hv_60d": round(hv_60, 4),
        "implied_vol": round(iv, 4),
        "iv_rank": round(iv_rank, 1),
        "hv_iv_ratio": round(hv_20 / iv, 3),
        "rsi_14": round(float(rng.uniform(20, 80)), 1),
        "macd_signal": round(float(rng.normal(0, 0.5)), 3),
        "bb_position": round(float(rng.uniform(-1.5, 1.5)), 3),   # Bollinger Band position
        "volume_ratio_20d": round(float(rng.lognormal(0, 0.3)), 3),
        "price_momentum_21d": round(float(rng.normal(0.02, 0.06)), 4),
        "pe_ratio": round(float(rng.uniform(8, 60)), 1),
        "revenue_growth_yoy": round(float(rng.normal(0.08, 0.15)), 4),
        "debt_to_equity": round(float(rng.uniform(0, 3)), 3),
        "free_cash_flow_yield": round(float(rng.uniform(-0.02, 0.10)), 4),
        "institutional_ownership": round(float(rng.uniform(0.30, 0.95)), 3),
        "short_interest": round(float(rng.uniform(0.01, 0.25)), 3),
        "analyst_consensus": round(float(rng.uniform(1.5, 4.5)), 2),  # 1=strong sell, 5=strong buy
        "earnings_surprise_recent": round(float(rng.normal(0.02, 0.08)), 4),
        "sentiment_score": round(float(rng.uniform(-1, 1)), 3),
        "macro_vix": round(float(rng.uniform(12, 45)), 1),
        "macro_10y_yield": round(float(rng.uniform(0.01, 0.05)), 4),
        "macro_dxy": round(float(rng.uniform(95, 115)), 1),
        "market_regime": _market_regime(),
    }


# ── Dataset 1: Confidence Calibrator ─────────────────────────────────────────

def generate_confidence_calibrator(n_samples: int = 15_000) -> pd.DataFrame:
    """
    Label schema:
      - reported_confidence: what the agent said
      - true_correct: 1 if the trade direction prediction was correct (binary)
      - calibration_gap: reported - actual accuracy (for regression target)

    Features: agent metadata + market context
    """
    records = []
    for _ in range(n_samples):
        reported_conf = _realistic_confidence()
        action = random.choice(["BUY", "BUY", "BUY", "SELL", "HOLD"])
        debate_rounds = _debate_rounds()
        market = _market_features()

        # True accuracy: depends on regime, IV, and some noise
        regime_bonus = {
            "bull": 0.06 if action == "BUY" else -0.06,
            "bear": 0.06 if action == "SELL" else -0.06,
            "sideways": -0.02,
            "volatile": -0.08,
            "recovery": 0.03,
        }.get(market["market_regime"], 0.0)

        iv_penalty = -0.04 if market["iv_rank"] > 70 else 0.02 if market["iv_rank"] < 30 else 0.0
        debate_bonus = min(debate_rounds * 0.02, 0.06)

        # True probability of being correct
        p_correct = float(np.clip(
            0.52 + (reported_conf - 0.65) * 0.4 + regime_bonus + iv_penalty + debate_bonus
            + float(rng.normal(0, 0.05)),
            0.1, 0.9
        ))
        true_correct = int(rng.binomial(1, p_correct))

        records.append({
            "reported_confidence": round(reported_conf, 4),
            "action": action,
            "debate_rounds": debate_rounds,
            "sharpe_context": round(market["hv_20d"] / max(market["implied_vol"], 0.01), 3),
            "iv_rank": market["iv_rank"],
            "rsi_14": market["rsi_14"],
            "sentiment_score": market["sentiment_score"],
            "momentum_21d": market["price_momentum_21d"],
            "market_regime": market["market_regime"],
            "macro_vix": market["macro_vix"],
            "analyst_consensus": market["analyst_consensus"],
            "earnings_surprise": market["earnings_surprise_recent"],
            "true_correct": true_correct,
            "calibration_gap": round(reported_conf - p_correct, 4),  # over/under confident
        })

    return pd.DataFrame(records)


# ── Dataset 2: Reward Predictor ───────────────────────────────────────────────

def generate_reward_predictor(n_samples: int = 12_000) -> pd.DataFrame:
    """
    Label schema:
      - reward_30d, reward_60d, reward_90d: RL reward at each horizon
        Reward = realized_return_pct - time_penalty (from trade_journal formula)
    """
    records = []
    for _ in range(n_samples):
        reported_conf = _realistic_confidence()
        action = random.choice(["BUY", "BUY", "SELL", "HOLD"])
        market = _market_features()

        # Base return: momentum + regime + fundamental quality
        regime_mult = {
            "bull": 0.8, "bear": -0.6, "sideways": 0.0,
            "volatile": 0.2, "recovery": 0.5
        }.get(market["market_regime"], 0.0)

        if action == "HOLD":
            regime_mult = 0.0

        direction_mult = 1.0 if action == "BUY" else (-1.0 if action == "SELL" else 0.0)
        fundamental_score = (
            market["revenue_growth_yoy"] * 0.5
            + market["free_cash_flow_yield"] * 0.3
            - market["debt_to_equity"] * 0.05
        )
        momentum_signal = market["price_momentum_21d"] * 0.3
        analyst_signal = (market["analyst_consensus"] - 3.0) / 2.0 * 0.1

        base_return = direction_mult * (
            regime_mult * 0.06
            + fundamental_score * 0.5
            + momentum_signal
            + analyst_signal
            + float(rng.normal(0, 0.04))
        )

        # Time decay: returns flatten out over time with mean-reversion
        def reward_at(days: int, noise_scale: float = 0.02) -> float:
            decay = 1.0 - (days - 30) / 120  # slight mean reversion
            time_penalty = 0.001 * (days / 30)
            raw = base_return * decay + float(rng.normal(0, noise_scale))
            return float(np.clip(raw - time_penalty, -0.5, 0.5))

        records.append({
            "reported_confidence": round(reported_conf, 4),
            "action": action,
            "debate_rounds": _debate_rounds(),
            "iv_rank": market["iv_rank"],
            "hv_20d": market["hv_20d"],
            "rsi_14": market["rsi_14"],
            "macd_signal": market["macd_signal"],
            "bb_position": market["bb_position"],
            "volume_ratio": market["volume_ratio_20d"],
            "momentum_21d": market["price_momentum_21d"],
            "revenue_growth": market["revenue_growth_yoy"],
            "fcf_yield": market["free_cash_flow_yield"],
            "short_interest": market["short_interest"],
            "sentiment_score": market["sentiment_score"],
            "macro_vix": market["macro_vix"],
            "macro_10y_yield": market["macro_10y_yield"],
            "market_regime": market["market_regime"],
            "reward_30d": round(reward_at(30, 0.015), 5),
            "reward_60d": round(reward_at(60, 0.025), 5),
            "reward_90d": round(reward_at(90, 0.035), 5),
        })

    return pd.DataFrame(records)


# ── Dataset 3: Options Pricer (IV Rank Predictor) ─────────────────────────────

def generate_options_pricer(n_samples: int = 10_000) -> pd.DataFrame:
    """
    Label schema:
      - iv_rank_bucket: 0 (low <30), 1 (moderate 30-70), 2 (high >70)
      - iv_rank_continuous: continuous target [0, 100]

    Features: market microstructure that predicts IV environment
    """
    records = []
    for _ in range(n_samples):
        market = _market_features()

        # IV rank is the label — reconstruct it with some noise for realism
        iv_rank = market["iv_rank"]
        # Add realistic label noise
        iv_rank_noisy = float(np.clip(iv_rank + rng.normal(0, 5), 0, 100))
        iv_rank_bucket = 0 if iv_rank_noisy < 30 else (2 if iv_rank_noisy > 70 else 1)

        records.append({
            "hv_20d": market["hv_20d"],
            "hv_60d": market["hv_60d"],
            "hv_iv_ratio": market["hv_iv_ratio"],
            "rsi_14": market["rsi_14"],
            "bb_position": market["bb_position"],
            "volume_ratio": market["volume_ratio_20d"],
            "momentum_21d": market["price_momentum_21d"],
            "short_interest": market["short_interest"],
            "macro_vix": market["macro_vix"],
            "macro_dxy": market["macro_dxy"],
            "market_regime": market["market_regime"],
            "earnings_surprise": market["earnings_surprise_recent"],
            "analyst_consensus": market["analyst_consensus"],
            "iv_rank_bucket": iv_rank_bucket,
            "iv_rank_continuous": round(iv_rank_noisy, 1),
        })

    return pd.DataFrame(records)


# ── Main generator ────────────────────────────────────────────────────────────

def generate_all(output_dir: Path | None = None, verbose: bool = True) -> dict[str, Path]:
    """Generate all 3 datasets and write to parquet."""
    base = output_dir or OUTPUT_DIR
    paths: dict[str, Path] = {}

    datasets = [
        ("confidence_calibrator", generate_confidence_calibrator, 15_000),
        ("reward_predictor", generate_reward_predictor, 12_000),
        ("options_pricer", generate_options_pricer, 10_000),
    ]

    for name, fn, n in datasets:
        out_dir = base / name
        out_dir.mkdir(parents=True, exist_ok=True)
        fpath = out_dir / "train.parquet"

        if verbose:
            logger.info("Generating %s (%d samples)...", name, n)

        df = fn(n)
        df.to_parquet(fpath, index=False)
        paths[name] = fpath

        if verbose:
            logger.info("  Saved %d rows → %s", len(df), fpath)

    return paths


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    paths = generate_all()
    print("\nGenerated:")
    for name, path in paths.items():
        df = pd.read_parquet(path)
        print(f"  {name}: {len(df):,} rows × {df.shape[1]} cols → {path}")
