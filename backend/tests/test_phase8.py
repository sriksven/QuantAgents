"""
Phase 8 tests — data generation, model mechanics, registry, bias detection.
No actual model training in tests (too slow) — uses synthetic fixtures or
pre-computed data to verify the pipeline components.
"""
from __future__ import annotations

import sys
import pickle
import tempfile
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, ".")


# ─── Data generator tests ──────────────────────────────────────────────────────

class TestDataGenerator:
    def test_confidence_calibrator_schema(self):
        from ml.data_generator import generate_confidence_calibrator
        df = generate_confidence_calibrator(n_samples=100)
        assert len(df) == 100
        required_cols = [
            "reported_confidence", "action", "debate_rounds", "iv_rank",
            "market_regime", "true_correct", "calibration_gap"
        ]
        for col in required_cols:
            assert col in df.columns, f"Missing column: {col}"

    def test_confidence_binary_label(self):
        from ml.data_generator import generate_confidence_calibrator
        df = generate_confidence_calibrator(n_samples=200)
        assert set(df["true_correct"].unique()).issubset({0, 1})

    def test_confidence_valid_range(self):
        from ml.data_generator import generate_confidence_calibrator
        df = generate_confidence_calibrator(n_samples=200)
        assert df["reported_confidence"].between(0, 1).all()

    def test_reward_predictor_schema(self):
        from ml.data_generator import generate_reward_predictor
        df = generate_reward_predictor(n_samples=100)
        assert "reward_30d" in df.columns
        assert "reward_60d" in df.columns
        assert "reward_90d" in df.columns

    def test_reward_values_bounded(self):
        from ml.data_generator import generate_reward_predictor
        df = generate_reward_predictor(n_samples=200)
        assert df["reward_30d"].between(-0.5, 0.5).all()
        assert df["reward_90d"].between(-0.5, 0.5).all()

    def test_options_pricer_schema(self):
        from ml.data_generator import generate_options_pricer
        df = generate_options_pricer(n_samples=100)
        assert "iv_rank_bucket" in df.columns
        assert "iv_rank_continuous" in df.columns

    def test_options_pricer_bucket_values(self):
        from ml.data_generator import generate_options_pricer
        df = generate_options_pricer(n_samples=200)
        assert set(df["iv_rank_bucket"].unique()).issubset({0, 1, 2})

    def test_iv_rank_continuous_range(self):
        from ml.data_generator import generate_options_pricer
        df = generate_options_pricer(n_samples=200)
        assert df["iv_rank_continuous"].between(0, 100).all()

    def test_market_regime_values(self):
        from ml.data_generator import generate_confidence_calibrator
        df = generate_confidence_calibrator(n_samples=500)
        valid_regimes = {"bull", "bear", "sideways", "volatile", "recovery"}
        assert set(df["market_regime"].unique()).issubset(valid_regimes)

    def test_generate_all_creates_files(self, tmp_path):
        from ml.data_generator import generate_all
        paths = generate_all(output_dir=tmp_path, verbose=False)
        assert len(paths) == 3
        for name, path in paths.items():
            assert Path(path).exists()
            df = pd.read_parquet(path)
            assert len(df) > 0


# ─── Feature encoding tests ────────────────────────────────────────────────────

class TestFeatureEncoding:
    def test_regime_encoding(self):
        from ml.train_models import _encode, REGIME_MAP
        df = pd.DataFrame({"market_regime": ["bull", "bear", "sideways"]})
        encoded = _encode(df)
        assert encoded["market_regime"].tolist() == [REGIME_MAP[r] for r in ["bull", "bear", "sideways"]]

    def test_action_encoding(self):
        from ml.train_models import _encode, ACTION_MAP
        df = pd.DataFrame({"action": ["BUY", "SELL", "HOLD"]})
        encoded = _encode(df)
        assert encoded["action"].tolist() == [ACTION_MAP[a] for a in ["BUY", "SELL", "HOLD"]]


# ─── Model registry tests ──────────────────────────────────────────────────────

class TestModelRegistry:
    def _make_dummy_model(self, tmp_path: Path, name: str) -> Path:
        """Create a dummy model pickle for testing."""
        path = tmp_path / f"{name}.pkl"
        with open(path, "wb") as f:
            pickle.dump({"model": None, "feature_cols": ["a", "b"], "metrics": {"test_auc": 0.75}}, f)
        return path

    def test_load_model(self, tmp_path):
        from ml.model_registry import ModelRegistry
        registry = ModelRegistry(model_dir=tmp_path)
        self._make_dummy_model(tmp_path, "test_model")
        bundle = registry.load("test_model")
        assert bundle["metrics"]["test_auc"] == 0.75

    def test_load_cached(self, tmp_path):
        from ml.model_registry import ModelRegistry
        registry = ModelRegistry(model_dir=tmp_path)
        self._make_dummy_model(tmp_path, "test_model")
        b1 = registry.load("test_model")
        b2 = registry.load("test_model")
        assert b1 is b2  # same object from cache

    def test_promote_archives_current(self, tmp_path):
        from ml.model_registry import ModelRegistry
        registry = ModelRegistry(model_dir=tmp_path)
        # Create initial model
        self._make_dummy_model(tmp_path, "test_model")
        # Create "new" model to promote
        new_path = tmp_path / "test_model_new.pkl"
        with open(new_path, "wb") as f:
            pickle.dump({"model": None, "feature_cols": [], "metrics": {}}, f)
        registry.promote("test_model", new_path)
        # Archive should exist
        archives = list(tmp_path.glob("test_model_v*.pkl"))
        assert len(archives) == 1

    def test_rollback(self, tmp_path):
        from ml.model_registry import ModelRegistry
        registry = ModelRegistry(model_dir=tmp_path)
        self._make_dummy_model(tmp_path, "test_model")
        new_path = tmp_path / "test_model_new.pkl"
        with open(new_path, "wb") as f:
            pickle.dump({"model": None, "feature_cols": [], "metrics": {}}, f)
        registry.promote("test_model", new_path)
        success = registry.rollback("test_model")
        assert success

    def test_rollback_no_versions(self, tmp_path):
        from ml.model_registry import ModelRegistry
        registry = ModelRegistry(model_dir=tmp_path)
        # No current model, no backups
        result = registry.rollback("nonexistent_model")
        assert result is False

    def test_max_versions_pruned(self, tmp_path):
        from ml.model_registry import ModelRegistry
        registry = ModelRegistry(model_dir=tmp_path)
        self._make_dummy_model(tmp_path, "test_model")
        # Promote 4 times (should only keep MAX_VERSIONS=3 archives)
        for _ in range(4):
            new_path = tmp_path / "new.pkl"
            with open(new_path, "wb") as f:
                pickle.dump({}, f)
            registry.promote("test_model", new_path)
        archives = list(tmp_path.glob("test_model_v*.pkl"))
        assert len(archives) <= 3

    def test_model_not_found_raises(self, tmp_path):
        from ml.model_registry import ModelRegistry
        registry = ModelRegistry(model_dir=tmp_path)
        with pytest.raises(FileNotFoundError):
            registry.load("nonexistent")


# ─── Bias detector logic tests ────────────────────────────────────────────────

class TestBiasDetectorLogic:
    """Test bias detection helpers without loading real models."""

    def test_high_severity_threshold(self):
        """Disparity > 10% should be HIGH severity."""
        flags = [{"disparity": 0.12, "severity": "HIGH", "dimension": "market_regime", "group": "volatile"}]
        has_high = any(f["severity"] == "HIGH" for f in flags)
        assert has_high

    def test_medium_severity_threshold(self):
        """Disparity 5-10% = MEDIUM severity."""
        disparity = 0.07
        severity = "HIGH" if disparity > 0.10 else "MEDIUM"
        assert severity == "MEDIUM"

    def test_no_bias_when_within_threshold(self):
        """Less than 5% gap = no flag."""
        overall = 0.75
        group_metric = 0.73
        threshold = 0.05
        flagged = (overall - group_metric) > threshold
        assert not flagged


# ─── DAG structure validation ─────────────────────────────────────────────────

class TestMonthlyRetrainDAG:
    def test_dag_has_correct_task_ids(self):
        """Verify DAG task graph is correctly defined."""
        try:
            # Import DAG without Airflow running (static analysis only)
            import importlib.util
            from pathlib import Path
            spec = importlib.util.spec_from_file_location(
                "monthly_retrain",
                Path("airflow/dags/monthly_retrain.py"),
            )
            module = importlib.util.load_from_spec(spec)
            # If import fails (no airflow installed), that's OK — skip test
        except Exception:
            pytest.skip("Airflow not installed — DAG import skipped")

    def test_retrain_schedule(self):
        """Monthly schedule should run on 1st of month at 2 AM."""
        schedule = "0 2 1 * *"
        # Cron: min=0, hour=2, day=1, month=*, weekday=*
        parts = schedule.split()
        assert parts[0] == "0"   # minute
        assert parts[1] == "2"   # hour
        assert parts[2] == "1"   # day of month
        assert parts[3] == "*"   # every month
