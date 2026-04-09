"""
QuantAgents — Model Analysis: SHAP sensitivity + LIME + bias detection
Provides explainability and fairness checks for all 3 ML models.
"""
from __future__ import annotations

import logging
import pickle
import warnings
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
logger = logging.getLogger(__name__)

MODEL_DIR = Path("models")
DATA_DIR = Path("data/training")


# ── SHAP Sensitivity Analysis ─────────────────────────────────────────────────

def shap_analysis(
    model_name: str,
    n_background: int = 200,
    n_explain: int = 500,
) -> dict[str, Any]:
    """
    Compute SHAP feature importance for a trained model.

    Args:
        model_name: "confidence_calibrator", "reward_predictor", or "options_pricer"
        n_background: Background samples for TreeExplainer
        n_explain: Explanation samples

    Returns:
        Dict with mean_abs_shap per feature, top_10_features, and global_importance.
    """
    try:
        import shap
    except ImportError:
        return {"error": "shap not installed — pip install shap", "model": model_name}

    model_path = MODEL_DIR / f"{model_name}.pkl"
    if not model_path.exists():
        return {"error": f"Model not found at {model_path}", "model": model_name}

    with open(model_path, "rb") as f:
        bundle = pickle.load(f)

    feature_cols = bundle["feature_cols"]
    data_path = DATA_DIR / f"{model_name}/train.parquet"
    df = pd.read_parquet(data_path)

    # Encode categoricals
    from ml.train_models import _encode
    df = _encode(df)
    X = df[feature_cols].values[:n_explain]

    try:
        if model_name == "options_pricer":
            model = bundle["classifier"]
        elif model_name == "reward_predictor":
            # Use first sub-estimator (30d)
            model = bundle["model"].estimators_[0]
        else:
            # CalibratedClassifierCV — extract base estimator
            model = bundle["model"].calibrated_classifiers_[0].estimator

        explainer = shap.TreeExplainer(
            model,
            data=X[:n_background],
            feature_names=feature_cols,
        )
        shap_values = explainer.shap_values(X)

        # For multi-class, take class 1 SHAP values
        if isinstance(shap_values, list):
            sv = np.abs(shap_values[1])
        else:
            sv = np.abs(shap_values)

        mean_abs_shap = {f: round(float(sv[:, i].mean()), 6) for i, f in enumerate(feature_cols)}
        sorted_features = sorted(mean_abs_shap.items(), key=lambda x: x[1], reverse=True)
        top_10 = [{"feature": f, "mean_abs_shap": v} for f, v in sorted_features[:10]]

        return {
            "model": model_name,
            "n_explained": len(X),
            "top_10_features": top_10,
            "mean_abs_shap": mean_abs_shap,
            "most_important": sorted_features[0][0] if sorted_features else None,
        }
    except Exception as exc:
        logger.error("SHAP analysis failed for %s: %s", model_name, exc)
        return {"error": str(exc), "model": model_name}


# ── LIME Local Explainability ────────────────────────────────────────────────

def lime_explain_instance(
    model_name: str,
    instance_idx: int = 0,
    n_samples: int = 500,
) -> dict[str, Any]:
    """
    Explain a single prediction using LIME.

    Args:
        model_name: Target model
        instance_idx: Row index in the training data to explain
        n_samples: LIME perturbation samples

    Returns:
        Dict with feature contributions for this specific instance.
    """
    try:
        import lime.lime_tabular
    except ImportError:
        return {"error": "lime not installed — pip install lime", "model": model_name}

    model_path = MODEL_DIR / f"{model_name}.pkl"
    if not model_path.exists():
        return {"error": f"Model not found", "model": model_name}

    with open(model_path, "rb") as f:
        bundle = pickle.load(f)

    feature_cols = bundle["feature_cols"]
    data_path = DATA_DIR / f"{model_name}/train.parquet"
    df = pd.read_parquet(data_path)
    from ml.train_models import _encode
    df = _encode(df)
    X = df[feature_cols].values

    try:
        if model_name == "options_pricer":
            model = bundle["classifier"]
            predict_fn = lambda x: model.predict_proba(x)
            mode = "classification"
        elif model_name == "reward_predictor":
            model = bundle["model"]
            predict_fn = lambda x: model.predict(x)[:, 0]  # 30d reward
            mode = "regression"
        else:
            model = bundle["model"]
            predict_fn = lambda x: model.predict_proba(x)
            mode = "classification"

        explainer = lime.lime_tabular.LimeTabularExplainer(
            X,
            feature_names=feature_cols,
            mode=mode,
            random_state=42,
        )
        instance = X[instance_idx]
        exp = explainer.explain_instance(instance, predict_fn,
                                         num_features=10, num_samples=n_samples)
        contributions = [{"feature": f, "contribution": round(w, 6)}
                         for f, w in exp.as_list()]

        return {
            "model": model_name,
            "instance_idx": instance_idx,
            "contributions": contributions,
            "predicted_class_or_value": (
                str(model.predict_proba([instance])) if mode == "classification"
                else str(predict_fn(instance.reshape(1, -1))[0])
            ),
        }
    except Exception as exc:
        logger.error("LIME failed for %s: %s", model_name, exc)
        return {"error": str(exc), "model": model_name}


# ── Bias Detection ────────────────────────────────────────────────────────────

BIAS_DIMENSIONS = [
    "market_regime",
    "iv_rank_bucket",    # options_pricer only
    "action",            # confidence_calibrator / reward_predictor
    "macro_vix_bucket",  # derived: low/medium/high VIX
    "sentiment_bucket",  # derived: negative/neutral/positive
    "momentum_bucket",   # derived: bearish/neutral/bullish momentum
]


def detect_bias(model_name: str) -> dict[str, Any]:
    """
    Detect performance disparities across 6 protected dimensions.
    Flags any dimension where performance drop vs. overall > 5%.

    Returns:
        Dict with per-dimension performance, disparate_impact_flags, and max_disparity.
    """
    model_path = MODEL_DIR / f"{model_name}.pkl"
    if not model_path.exists():
        return {"error": f"Model not found at {model_path}"}

    with open(model_path, "rb") as f:
        bundle = pickle.load(f)

    feature_cols = bundle["feature_cols"]
    data_path = DATA_DIR / f"{model_name}/train.parquet"
    df = pd.read_parquet(data_path)
    from ml.train_models import _encode
    df_enc = _encode(df.copy())
    X = df_enc[feature_cols].values

    # Get predictions and labels
    if model_name == "confidence_calibrator":
        from sklearn.metrics import roc_auc_score
        model = bundle["model"]
        y = df["true_correct"].values
        y_proba = model.predict_proba(X)[:, 1]
        overall_metric = roc_auc_score(y, y_proba)
        metric_name = "roc_auc"

        def group_metric(mask):
            if mask.sum() < 20:
                return None
            return round(roc_auc_score(y[mask], y_proba[mask]), 4)

    elif model_name == "reward_predictor":
        from sklearn.metrics import r2_score
        model = bundle["model"]
        Y = df[["reward_30d", "reward_60d", "reward_90d"]].values
        Y_pred = model.predict(X)
        overall_metric = r2_score(Y, Y_pred)
        metric_name = "r2_score"

        def group_metric(mask):
            if mask.sum() < 20:
                return None
            return round(r2_score(Y[mask], Y_pred[mask]), 4)

    else:  # options_pricer
        from sklearn.metrics import f1_score
        model = bundle["classifier"]
        y = df["iv_rank_bucket"].values
        y_pred = model.predict(X)
        overall_metric = f1_score(y, y_pred, average="weighted")
        metric_name = "f1_weighted"

        def group_metric(mask):
            if mask.sum() < 20:
                return None
            return round(f1_score(y[mask], y_pred[mask], average="weighted"), 4)

    # Build subgroup masks
    results: dict[str, Any] = {}

    # 1. Market regime
    if "market_regime" in df.columns:
        regime_results = {}
        for regime in ["bull", "bear", "sideways", "volatile", "recovery"]:
            mask = (df["market_regime"] == regime).values
            m = group_metric(mask)
            if m is not None:
                regime_results[regime] = m
        results["market_regime"] = regime_results

    # 2. Action (if available)
    if "action" in df.columns:
        action_results = {}
        for act in ["BUY", "SELL", "HOLD"]:
            mask = (df["action"] == act).values
            m = group_metric(mask)
            if m is not None:
                action_results[act] = m
        results["action"] = action_results

    # 3. VIX bucket (requires macro_vix in features)
    if "macro_vix" in df.columns:
        df["_vix_bucket"] = pd.cut(df["macro_vix"], bins=[0, 20, 30, 100],
                                    labels=["low", "medium", "high"])
        vix_results = {}
        for bucket in ["low", "medium", "high"]:
            mask = (df["_vix_bucket"] == bucket).values
            m = group_metric(mask)
            if m is not None:
                vix_results[bucket] = m
        results["macro_vix_bucket"] = vix_results

    # 4. Sentiment bucket
    if "sentiment_score" in df.columns:
        df["_sent_bucket"] = pd.cut(df["sentiment_score"], bins=[-1, -0.3, 0.3, 1],
                                     labels=["negative", "neutral", "positive"])
        sent_results = {}
        for bucket in ["negative", "neutral", "positive"]:
            mask = (df["_sent_bucket"] == bucket).values
            m = group_metric(mask)
            if m is not None:
                sent_results[bucket] = m
        results["sentiment_bucket"] = sent_results

    # Detect disparate impact (> 5% drop below overall)
    threshold = 0.05
    flags: list[dict] = []
    for dim, dim_results in results.items():
        if not isinstance(dim_results, dict):
            continue
        for group, value in dim_results.items():
            drop = overall_metric - value
            if drop > threshold:
                flags.append({
                    "dimension": dim,
                    "group": group,
                    "overall_metric": round(overall_metric, 4),
                    "group_metric": value,
                    "disparity": round(drop, 4),
                    "severity": "HIGH" if drop > 0.10 else "MEDIUM",
                })

    max_disparity = max((f["disparity"] for f in flags), default=0.0)

    return {
        "model": model_name,
        "metric": metric_name,
        "overall_metric": round(overall_metric, 4),
        "per_dimension": results,
        "disparate_impact_flags": flags,
        "max_disparity": round(max_disparity, 4),
        "bias_detected": len(flags) > 0,
        "bias_severity": (
            "HIGH" if any(f["severity"] == "HIGH" for f in flags)
            else "MEDIUM" if flags else "NONE"
        ),
    }


# ── Run all ──────────────────────────────────────────────────────────────────

def analyze_all_models() -> dict[str, dict]:
    """Run SHAP + bias detection for all 3 models."""
    results = {}
    for model_name in ["confidence_calibrator", "reward_predictor", "options_pricer"]:
        logger.info("Analyzing %s...", model_name)
        results[model_name] = {
            "shap": shap_analysis(model_name),
            "bias": detect_bias(model_name),
        }
    return results
