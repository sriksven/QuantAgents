"""
QuantAgents — Model Registry + Inference Service
Handles versioned model loading, inference caching, rollback,
and the monthly retrain Airflow DAG trigger.
"""

from __future__ import annotations

import logging
import os
import pickle
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

MODEL_DIR = Path(os.getenv("MODEL_DIR", "models"))


# ── Model Registry ────────────────────────────────────────────────────────────


class ModelRegistry:
    """
    Simple file-based model registry with versioning + rollback.

    Directory structure:
        models/
          confidence_calibrator.pkl         # current production model
          confidence_calibrator_v{N}.pkl    # versioned snapshots (keep last 3)
          reward_predictor.pkl
          options_pricer.pkl

    In production, swap this for MLflow Model Registry.
    """

    MAX_VERSIONS = 3

    def __init__(self, model_dir: Path = MODEL_DIR):
        self.model_dir = model_dir
        self._cache: dict[str, Any] = {}

    def load(self, model_name: str, force_reload: bool = False) -> Any:
        """Load a model from registry, using in-process cache."""
        if model_name in self._cache and not force_reload:
            return self._cache[model_name]

        path = self.model_dir / f"{model_name}.pkl"
        if not path.exists():
            raise FileNotFoundError(f"Model not found: {path}")

        with open(path, "rb") as f:
            bundle = pickle.load(f)

        self._cache[model_name] = bundle
        logger.info("Loaded model: %s", model_name)
        return bundle

    def promote(self, model_name: str, new_model_path: Path) -> None:
        """
        Promote a new model to production.
        Archives the current version before overwriting.
        """
        current = self.model_dir / f"{model_name}.pkl"
        if current.exists():
            # Find next version number
            existing = sorted(self.model_dir.glob(f"{model_name}_v*.pkl"))
            next_v = len(existing) + 1
            archive = self.model_dir / f"{model_name}_v{next_v}.pkl"
            current.rename(archive)
            logger.info("Archived current %s → %s", model_name, archive.name)

            # Prune old versions (keep last MAX_VERSIONS)
            existing = sorted(self.model_dir.glob(f"{model_name}_v*.pkl"))
            for old in existing[: -self.MAX_VERSIONS]:
                old.unlink()
                logger.info("Pruned old version: %s", old.name)

        # Copy new model to production slot
        import shutil

        shutil.copy2(new_model_path, current)
        self._cache.pop(model_name, None)  # invalidate cache
        logger.info("Promoted %s → %s", new_model_path, current)

    def rollback(self, model_name: str) -> bool:
        """Rollback to the previous version."""
        versions = sorted(self.model_dir.glob(f"{model_name}_v*.pkl"), reverse=True)
        if not versions:
            logger.warning("No rollback versions found for %s", model_name)
            return False

        latest_backup = versions[0]
        current = self.model_dir / f"{model_name}.pkl"
        latest_backup.rename(current)
        self._cache.pop(model_name, None)
        logger.info("Rolled back %s to %s", model_name, latest_backup.name)
        return True

    def list_versions(self, model_name: str) -> list[str]:
        """List all available versions of a model."""
        current = self.model_dir / f"{model_name}.pkl"
        backups = sorted(self.model_dir.glob(f"{model_name}_v*.pkl"))
        result = []
        if current.exists():
            result.append(f"{model_name}.pkl [CURRENT]")
        for b in backups:
            result.append(str(b.name))
        return result


# ── Inference Service ─────────────────────────────────────────────────────────

_registry = ModelRegistry()


def predict_confidence(
    reported_confidence: float,
    action: str,
    debate_rounds: int,
    iv_rank: float,
    rsi_14: float,
    sentiment_score: float,
    momentum_21d: float,
    market_regime: str,
    macro_vix: float,
    analyst_consensus: float,
    earnings_surprise: float,
) -> dict[str, Any]:
    """
    Calibrate agent-reported confidence using the trained Confidence Calibrator.

    Returns:
        calibrated_confidence, reliability_score, is_overconfident (bool)
    """
    from ml.train_models import ACTION_MAP, REGIME_MAP

    try:
        bundle = _registry.load("confidence_calibrator")
        model = bundle["model"]
        feature_cols = bundle["feature_cols"]

        row = {
            "reported_confidence": reported_confidence,
            "action": ACTION_MAP.get(action.upper(), 2),
            "debate_rounds": debate_rounds,
            "sharpe_context": 1.0,
            "iv_rank": iv_rank,
            "rsi_14": rsi_14,
            "sentiment_score": sentiment_score,
            "momentum_21d": momentum_21d,
            "market_regime": REGIME_MAP.get(market_regime, 2),
            "macro_vix": macro_vix,
            "analyst_consensus": analyst_consensus,
            "earnings_surprise": earnings_surprise,
        }

        X = np.array([[row.get(f, 0) for f in feature_cols]])
        proba = float(model.predict_proba(X)[0, 1])
        is_overconfident = proba < reported_confidence - 0.10

        return {
            "reported_confidence": round(reported_confidence, 4),
            "calibrated_confidence": round(proba, 4),
            "calibration_gap": round(reported_confidence - proba, 4),
            "is_overconfident": is_overconfident,
            "reliability_score": round(proba, 4),
        }
    except Exception as exc:
        logger.error("predict_confidence failed: %s", exc)
        return {"error": str(exc), "reported_confidence": reported_confidence}


def predict_reward(
    reported_confidence: float,
    action: str,
    debate_rounds: int,
    iv_rank: float,
    hv_20d: float,
    rsi_14: float,
    macd_signal: float,
    bb_position: float,
    volume_ratio: float,
    momentum_21d: float,
    revenue_growth: float,
    fcf_yield: float,
    short_interest: float,
    sentiment_score: float,
    macro_vix: float,
    macro_10y_yield: float,
    market_regime: str,
) -> dict[str, Any]:
    """
    Predict the 30/60/90-day RL reward for a trade setup.

    Returns:
        reward_30d, reward_60d, reward_90d (predicted), best_horizon, expected_best_reward
    """
    from ml.train_models import ACTION_MAP, REGIME_MAP

    try:
        bundle = _registry.load("reward_predictor")
        model = bundle["model"]
        feature_cols = bundle["feature_cols"]

        row = {
            "reported_confidence": reported_confidence,
            "action": ACTION_MAP.get(action.upper(), 2),
            "debate_rounds": debate_rounds,
            "iv_rank": iv_rank,
            "hv_20d": hv_20d,
            "rsi_14": rsi_14,
            "macd_signal": macd_signal,
            "bb_position": bb_position,
            "volume_ratio": volume_ratio,
            "momentum_21d": momentum_21d,
            "revenue_growth": revenue_growth,
            "fcf_yield": fcf_yield,
            "short_interest": short_interest,
            "sentiment_score": sentiment_score,
            "macro_vix": macro_vix,
            "macro_10y_yield": macro_10y_yield,
            "market_regime": REGIME_MAP.get(market_regime, 2),
        }

        X = np.array([[row.get(f, 0) for f in feature_cols]])
        preds = model.predict(X)[0]
        best_idx = int(np.argmax(preds))
        horizons = ["30d", "60d", "90d"]

        return {
            "reward_30d": round(float(preds[0]), 5),
            "reward_60d": round(float(preds[1]), 5),
            "reward_90d": round(float(preds[2]), 5),
            "best_horizon": horizons[best_idx],
            "expected_best_reward": round(float(preds[best_idx]), 5),
        }
    except Exception as exc:
        logger.error("predict_reward failed: %s", exc)
        return {"error": str(exc)}


def predict_iv_rank(
    hv_20d: float,
    hv_60d: float,
    rsi_14: float,
    bb_position: float,
    volume_ratio: float,
    momentum_21d: float,
    short_interest: float,
    macro_vix: float,
    macro_dxy: float,
    market_regime: str,
    earnings_surprise: float,
    analyst_consensus: float,
) -> dict[str, Any]:
    """
    Predict IV rank bucket and continuous IV rank for options strategy selection.

    Returns:
        iv_rank_bucket (0/1/2), iv_rank_continuous, iv_environment, confidence_scores
    """
    from ml.train_models import REGIME_MAP

    try:
        bundle = _registry.load("options_pricer")
        classifier = bundle["classifier"]
        regressor = bundle["regressor"]
        feature_cols = bundle["feature_cols"]

        row = {
            "hv_20d": hv_20d,
            "hv_60d": hv_60d,
            "hv_iv_ratio": hv_20d / max(hv_20d * 1.1, 0.01),  # rough proxy
            "rsi_14": rsi_14,
            "bb_position": bb_position,
            "volume_ratio": volume_ratio,
            "momentum_21d": momentum_21d,
            "short_interest": short_interest,
            "macro_vix": macro_vix,
            "macro_dxy": macro_dxy,
            "market_regime": REGIME_MAP.get(market_regime, 2),
            "earnings_surprise": earnings_surprise,
            "analyst_consensus": analyst_consensus,
        }

        X = np.array([[row.get(f, 0) for f in feature_cols]])
        bucket = int(classifier.predict(X)[0])
        proba = classifier.predict_proba(X)[0]
        iv_rank_cont = float(regressor.predict(X)[0])
        iv_env = ["low", "moderate", "high"][bucket]

        return {
            "iv_rank_bucket": bucket,
            "iv_rank_continuous": round(np.clip(iv_rank_cont, 0, 100), 1),
            "iv_environment": iv_env,
            "confidence_scores": {
                "low": round(float(proba[0]), 4),
                "moderate": round(float(proba[1]), 4),
                "high": round(float(proba[2]), 4),
            },
        }
    except Exception as exc:
        logger.error("predict_iv_rank failed: %s", exc)
        return {"error": str(exc)}


# ── Registry singleton accessor ───────────────────────────────────────────────


def get_registry() -> ModelRegistry:
    return _registry
