"""
QuantAgents — Model Training Pipeline
Trains all 3 ML models with Optuna hyperparameter tuning and MLflow tracking.

Models:
  1. Confidence Calibrator  — XGBoost classifier, labels: true_correct
  2. Reward Predictor       — XGBoost regressor, multi-target (30/60/90d rewards)
  3. Options Pricer         — XGBoost multi-class (IV rank bucket 0/1/2)
"""

from __future__ import annotations

import logging
import os
import pickle
import warnings
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
logger = logging.getLogger(__name__)

DATA_DIR = Path("data/training")
MODEL_DIR = Path("models")
MLFLOW_URI = os.getenv("MLFLOW_TRACKING_URI", "sqlite:///mlflow.db")
EXPERIMENT_NAME = "QuantAgents-Models"


# ── Feature encoding ──────────────────────────────────────────────────────────

REGIME_MAP = {"bull": 0, "bear": 1, "sideways": 2, "volatile": 3, "recovery": 4}
ACTION_MAP = {"BUY": 0, "SELL": 1, "HOLD": 2}


def _encode(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    if "market_regime" in df.columns:
        df["market_regime"] = df["market_regime"].map(REGIME_MAP).fillna(2)
    if "action" in df.columns:
        df["action"] = df["action"].map(ACTION_MAP).fillna(2)
    return df


# ── Optuna + XGBoost training helpers ─────────────────────────────────────────


def _xgb_trial_params(trial) -> dict[str, Any]:
    """Shared Optuna search space for XGBoost."""
    import optuna  # noqa

    return {
        "n_estimators": trial.suggest_int("n_estimators", 100, 600),
        "max_depth": trial.suggest_int("max_depth", 3, 8),
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.2, log=True),
        "subsample": trial.suggest_float("subsample", 0.6, 1.0),
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.5, 1.0),
        "min_child_weight": trial.suggest_int("min_child_weight", 1, 10),
        "gamma": trial.suggest_float("gamma", 0, 0.5),
        "reg_alpha": trial.suggest_float("reg_alpha", 1e-4, 1.0, log=True),
        "reg_lambda": trial.suggest_float("reg_lambda", 1e-4, 1.0, log=True),
        "random_state": 42,
        "tree_method": "hist",
        "n_jobs": -1,
    }


# ── Model 1: Confidence Calibrator ────────────────────────────────────────────


def train_confidence_calibrator(
    n_trials: int = 30,
    cv_folds: int = 5,
    track_mlflow: bool = True,
) -> dict[str, Any]:
    """
    Binary classifier: given reported confidence + market features → predict true_correct.
    Also trains isotonic regression as a calibration wrapper.
    """
    import optuna
    import xgboost as xgb
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.metrics import brier_score_loss, roc_auc_score
    from sklearn.model_selection import StratifiedKFold, cross_val_score

    optuna.logging.set_verbosity(optuna.logging.WARNING)

    df = pd.read_parquet(DATA_DIR / "confidence_calibrator/train.parquet")
    df = _encode(df)

    feature_cols = [c for c in df.columns if c not in ("true_correct", "calibration_gap")]
    X = df[feature_cols].values
    y = df["true_correct"].values

    def objective(trial):
        params = _xgb_trial_params(trial)
        model = xgb.XGBClassifier(**params, eval_metric="logloss", verbosity=0)
        cv = StratifiedKFold(n_splits=cv_folds, shuffle=True, random_state=42)
        scores = cross_val_score(model, X, y, cv=cv, scoring="roc_auc")
        return scores.mean()

    study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=42))
    study.optimize(objective, n_trials=n_trials, show_progress_bar=False)

    # Train final model with best params
    xgb_model = xgb.XGBClassifier(
        n_estimators=study.best_params["n_estimators"],
        max_depth=study.best_params["max_depth"],
        learning_rate=study.best_params["learning_rate"],
        subsample=study.best_params["subsample"],
        colsample_bytree=study.best_params["colsample_bytree"],
        min_child_weight=study.best_params["min_child_weight"],
        gamma=study.best_params["gamma"],
        reg_alpha=study.best_params["reg_alpha"],
        reg_lambda=study.best_params["reg_lambda"],
        random_state=42,
        tree_method="hist",
        n_jobs=-1,
        eval_metric="logloss",
        verbosity=0,
    )

    # Isotonic calibration wrapper
    calibrated = CalibratedClassifierCV(xgb_model, method="isotonic", cv=5)
    calibrated.fit(X, y)

    # Evaluate on held-out 20%
    from sklearn.model_selection import train_test_split

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    eval_model = CalibratedClassifierCV(
        xgb.XGBClassifier(
            **{
                k: study.best_params.get(k, v)
                for k, v in {
                    "n_estimators": 200,
                    "max_depth": 5,
                    "learning_rate": 0.05,
                    "subsample": 0.8,
                    "colsample_bytree": 0.8,
                    "min_child_weight": 3,
                    "gamma": 0.1,
                    "reg_alpha": 0.01,
                    "reg_lambda": 0.1,
                    "random_state": 42,
                    "tree_method": "hist",
                    "n_jobs": -1,
                    "eval_metric": "logloss",
                    "verbosity": 0,
                }.items()
            }
        ),
        method="isotonic",
        cv=5,
    )
    eval_model.fit(X_train, y_train)
    y_proba = eval_model.predict_proba(X_test)[:, 1]
    auc = roc_auc_score(y_test, y_proba)
    brier = brier_score_loss(y_test, y_proba)

    metrics = {
        "model": "confidence_calibrator",
        "best_cv_auc": round(study.best_value, 4),
        "test_auc": round(auc, 4),
        "test_brier_score": round(brier, 4),
        "n_features": len(feature_cols),
        "n_samples": len(df),
        "feature_cols": feature_cols,
    }

    # Save model
    model_path = MODEL_DIR / "confidence_calibrator.pkl"
    model_path.parent.mkdir(parents=True, exist_ok=True)
    with open(model_path, "wb") as f:
        pickle.dump({"model": calibrated, "feature_cols": feature_cols, "metrics": metrics}, f)

    if track_mlflow:
        _log_to_mlflow("confidence_calibrator", study.best_params, metrics, model_path)

    logger.info("Confidence Calibrator: AUC=%.3f, Brier=%.3f", auc, brier)
    return metrics


# ── Model 2: Reward Predictor ─────────────────────────────────────────────────


def train_reward_predictor(
    n_trials: int = 30,
    cv_folds: int = 5,
    track_mlflow: bool = True,
) -> dict[str, Any]:
    """
    Multi-output regressor: predicts 30/60/90d RL reward.
    Uses separate XGBoost regressors per horizon wrapped in MultiOutputRegressor.
    """
    import optuna
    import xgboost as xgb
    from sklearn.metrics import mean_absolute_error, r2_score
    from sklearn.model_selection import KFold, cross_val_score
    from sklearn.multioutput import MultiOutputRegressor

    optuna.logging.set_verbosity(optuna.logging.WARNING)

    df = pd.read_parquet(DATA_DIR / "reward_predictor/train.parquet")
    df = _encode(df)

    target_cols = ["reward_30d", "reward_60d", "reward_90d"]
    feature_cols = [c for c in df.columns if c not in target_cols]
    X = df[feature_cols].values
    Y = df[target_cols].values

    def objective(trial):
        params = _xgb_trial_params(trial)
        model = MultiOutputRegressor(xgb.XGBRegressor(**params, verbosity=0))
        cv = KFold(n_splits=cv_folds, shuffle=True, random_state=42)
        scores = cross_val_score(model, X, Y, cv=cv, scoring="r2")
        return scores.mean()

    study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=42))
    study.optimize(objective, n_trials=n_trials, show_progress_bar=False)

    # Train final model
    final_xgb = xgb.XGBRegressor(
        **{
            k: study.best_params.get(k)
            for k in [
                "n_estimators",
                "max_depth",
                "learning_rate",
                "subsample",
                "colsample_bytree",
                "min_child_weight",
                "gamma",
                "reg_alpha",
                "reg_lambda",
            ]
            if k in study.best_params
        },
        random_state=42,
        tree_method="hist",
        n_jobs=-1,
        verbosity=0,
    )
    final_model = MultiOutputRegressor(final_xgb)
    final_model.fit(X, Y)

    # Eval on 20% holdout
    from sklearn.model_selection import train_test_split

    X_tr, X_te, Y_tr, Y_te = train_test_split(X, Y, test_size=0.2, random_state=42)
    final_model.fit(X_tr, Y_tr)
    Y_pred = final_model.predict(X_te)
    per_target_r2 = [round(r2_score(Y_te[:, i], Y_pred[:, i]), 4) for i in range(3)]
    per_target_mae = [round(mean_absolute_error(Y_te[:, i], Y_pred[:, i]), 5) for i in range(3)]

    metrics = {
        "model": "reward_predictor",
        "best_cv_r2": round(study.best_value, 4),
        "r2_30d": per_target_r2[0],
        "r2_60d": per_target_r2[1],
        "r2_90d": per_target_r2[2],
        "mae_30d": per_target_mae[0],
        "mae_60d": per_target_mae[1],
        "mae_90d": per_target_mae[2],
        "n_features": len(feature_cols),
        "n_samples": len(df),
        "feature_cols": feature_cols,
    }

    model_path = MODEL_DIR / "reward_predictor.pkl"
    model_path.parent.mkdir(parents=True, exist_ok=True)
    with open(model_path, "wb") as f:
        pickle.dump({"model": final_model, "feature_cols": feature_cols, "metrics": metrics}, f)

    if track_mlflow:
        _log_to_mlflow("reward_predictor", study.best_params, metrics, model_path)

    logger.info("Reward Predictor: R² 30d=%.3f / 60d=%.3f / 90d=%.3f", *per_target_r2)
    return metrics


# ── Model 3: Options Pricer (IV Rank Classifier) ──────────────────────────────


def train_options_pricer(
    n_trials: int = 25,
    cv_folds: int = 5,
    track_mlflow: bool = True,
) -> dict[str, Any]:
    """
    Multi-class classifier: Low / Moderate / High IV rank (0/1/2).
    Also exports a regression head for continuous IV rank.
    """
    import optuna
    import xgboost as xgb
    from sklearn.metrics import accuracy_score, f1_score
    from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split

    optuna.logging.set_verbosity(optuna.logging.WARNING)

    df = pd.read_parquet(DATA_DIR / "options_pricer/train.parquet")
    df = _encode(df)

    feature_cols = [c for c in df.columns if c not in ("iv_rank_bucket", "iv_rank_continuous")]
    X = df[feature_cols].values
    y_cls = df["iv_rank_bucket"].values
    y_reg = df["iv_rank_continuous"].values

    def objective(trial):
        params = _xgb_trial_params(trial)
        model = xgb.XGBClassifier(
            **params,
            objective="multi:softprob",
            num_class=3,
            eval_metric="mlogloss",
            verbosity=0,
        )
        cv = StratifiedKFold(n_splits=cv_folds, shuffle=True, random_state=42)
        scores = cross_val_score(model, X, y_cls, cv=cv, scoring="f1_weighted")
        return scores.mean()

    study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=42))
    study.optimize(objective, n_trials=n_trials, show_progress_bar=False)

    # Train final classifier
    clf = xgb.XGBClassifier(
        **{
            k: study.best_params.get(k)
            for k in [
                "n_estimators",
                "max_depth",
                "learning_rate",
                "subsample",
                "colsample_bytree",
                "min_child_weight",
                "gamma",
                "reg_alpha",
                "reg_lambda",
            ]
            if k in study.best_params
        },
        objective="multi:softprob",
        num_class=3,
        eval_metric="mlogloss",
        random_state=42,
        tree_method="hist",
        n_jobs=-1,
        verbosity=0,
    )

    # Train regression head separately
    reg = xgb.XGBRegressor(
        **{
            k: study.best_params.get(k)
            for k in [
                "n_estimators",
                "max_depth",
                "learning_rate",
                "subsample",
                "colsample_bytree",
                "min_child_weight",
                "gamma",
                "reg_alpha",
                "reg_lambda",
            ]
            if k in study.best_params
        },
        random_state=42,
        tree_method="hist",
        n_jobs=-1,
        verbosity=0,
    )

    X_tr, X_te, y_tr, y_te, yr_tr, yr_te = train_test_split(
        X, y_cls, y_reg, test_size=0.2, random_state=42, stratify=y_cls
    )
    clf.fit(X_tr, y_tr)
    reg.fit(X_tr, yr_tr)

    y_pred = clf.predict(X_te)
    f1 = f1_score(y_te, y_pred, average="weighted")
    acc = accuracy_score(y_te, y_pred)

    from sklearn.metrics import mean_absolute_error

    yr_pred = reg.predict(X_te)
    mae_rank = mean_absolute_error(yr_te, yr_pred)

    metrics = {
        "model": "options_pricer",
        "best_cv_f1": round(study.best_value, 4),
        "test_f1_weighted": round(f1, 4),
        "test_accuracy": round(acc, 4),
        "test_mae_iv_rank": round(mae_rank, 2),
        "class_distribution": {
            str(k): int(v) for k, v in zip(*np.unique(y_cls, return_counts=True), strict=True)
        },
        "n_features": len(feature_cols),
        "n_samples": len(df),
        "feature_cols": feature_cols,
    }

    model_path = MODEL_DIR / "options_pricer.pkl"
    model_path.parent.mkdir(parents=True, exist_ok=True)
    with open(model_path, "wb") as f:
        pickle.dump(
            {
                "classifier": clf,
                "regressor": reg,
                "feature_cols": feature_cols,
                "metrics": metrics,
            },
            f,
        )

    if track_mlflow:
        _log_to_mlflow("options_pricer", study.best_params, metrics, model_path)

    logger.info("Options Pricer: F1=%.3f, Acc=%.3f, IV Rank MAE=%.1f", f1, acc, mae_rank)
    return metrics


# ── MLflow logging ────────────────────────────────────────────────────────────


def _log_to_mlflow(model_name: str, params: dict, metrics: dict, model_path: Path):
    try:
        import mlflow

        mlflow.set_tracking_uri(MLFLOW_URI)
        mlflow.set_experiment(EXPERIMENT_NAME)

        with mlflow.start_run(run_name=model_name):
            # Log hyperparameters
            for k, v in params.items():
                mlflow.log_param(k, v)
            # Log metrics (skip non-numeric)
            for k, v in metrics.items():
                if isinstance(v, (int, float)) and k != "n_samples":
                    mlflow.log_metric(k, v)
            mlflow.log_param("n_samples", metrics.get("n_samples", 0))
            # Log model artifact
            mlflow.log_artifact(str(model_path), artifact_path="model")
    except Exception as exc:
        logger.warning("MLflow logging skipped: %s", exc)


# ── Main ─────────────────────────────────────────────────────────────────────


def train_all(n_trials: int = 30, track_mlflow: bool = True) -> dict[str, dict]:
    """Train all 3 models end-to-end."""
    results = {}
    for train_fn, name in [
        (
            lambda: train_confidence_calibrator(n_trials, track_mlflow=track_mlflow),
            "confidence_calibrator",
        ),
        (lambda: train_reward_predictor(n_trials, track_mlflow=track_mlflow), "reward_predictor"),
        (lambda: train_options_pricer(n_trials, track_mlflow=track_mlflow), "options_pricer"),
    ]:
        logger.info("Training %s...", name)
        results[name] = train_fn()
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="[%(name)s] %(message)s")
    from ml.data_generator import generate_all

    logger.info("Generating training data...")
    generate_all()
    logger.info("Training all models (30 Optuna trials each)...")
    results = train_all(n_trials=30)
    print("\n── Training Summary ──────────────────────────")
    for name, m in results.items():
        print(f"  {name}:")
        for k, v in m.items():
            if isinstance(v, (int, float)):
                print(f"    {k}: {v}")
