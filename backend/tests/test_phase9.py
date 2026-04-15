"""
Phase 9 tests — CI/CD workflow structure validation.
Validates YAML syntax, required fields, job dependencies, trigger conditions,
and environment variables for all 5 GitHub Actions workflows.

NOTE: PyYAML parses YAML's reserved 'on:' key as Python boolean True.
Use w[True] or the _triggers() helper everywhere instead of w["on"].
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, ".")

WORKFLOWS_DIR = Path(".github/workflows")


def _load(filename: str) -> dict:
    path = WORKFLOWS_DIR / filename
    if not path.exists():
        pytest.skip(f"Workflow not found: {path}")
    with open(path) as f:
        return yaml.safe_load(f)


def _triggers(w: dict) -> dict:
    """Return the 'on:' block (PyYAML parses this as boolean True)."""
    return w.get(True, w.get("on", {})) or {}


# ─── tests.yml ────────────────────────────────────────────────────────────────


class TestTestsWorkflow:
    def test_triggers_on_push_and_pr(self):
        w = _load("tests.yml")
        triggers = _triggers(w)
        assert "push" in triggers
        assert "pull_request" in triggers

    def test_has_lint_job(self):
        w = _load("tests.yml")
        assert "lint" in w["jobs"]

    def test_has_test_job_with_matrix(self):
        w = _load("tests.yml")
        assert "test" in w["jobs"]
        test_job = w["jobs"]["test"]
        assert "matrix" in test_job.get("strategy", {})
        phases = test_job["strategy"]["matrix"].get("phase", [])
        # Should cover Phase 2-8
        assert "2" in phases
        assert "8" in phases
        assert len(phases) >= 7

    def test_matrix_fail_fast_disabled(self):
        """fail-fast: false ensures all phases run even if one fails."""
        w = _load("tests.yml")
        assert w["jobs"]["test"]["strategy"].get("fail-fast") is False

    def test_has_postgres_service(self):
        w = _load("tests.yml")
        services = w["jobs"]["test"].get("services", {})
        assert "postgres" in services

    def test_has_redis_service(self):
        w = _load("tests.yml")
        services = w["jobs"]["test"].get("services", {})
        assert "redis" in services

    def test_has_coverage_gate_job(self):
        w = _load("tests.yml")
        job_ids = list(w["jobs"].keys())
        # Coverage gate job exists
        assert any("coverage" in j for j in job_ids)

    def test_has_failure_notification(self):
        w = _load("tests.yml")
        # should have a notify-on-failure job
        assert any("notify" in j.lower() for j in w["jobs"])

    def test_test_job_needs_lint(self):
        w = _load("tests.yml")
        needs = w["jobs"]["test"].get("needs", [])
        if isinstance(needs, str):
            needs = [needs]
        assert "lint" in needs


# ─── data_pipeline.yml ────────────────────────────────────────────────────────


class TestDataPipelineWorkflow:
    def test_scheduled_trigger(self):
        w = _load("data_pipeline.yml")
        schedule = _triggers(w).get("schedule", [])
        assert len(schedule) >= 1
        cron = schedule[0].get("cron", "")
        assert "1-5" in cron  # Mon-Fri

    def test_has_workflow_dispatch(self):
        w = _load("data_pipeline.yml")
        assert "workflow_dispatch" in _triggers(w)

    def test_dispatch_has_dry_run_input(self):
        w = _load("data_pipeline.yml")
        inputs = _triggers(w).get("workflow_dispatch", {}).get("inputs", {})
        assert "dry_run" in inputs

    def test_has_alpha_vantage_secret(self):
        yaml_text = (WORKFLOWS_DIR / "data_pipeline.yml").read_text()
        assert "ALPHA_VANTAGE_API_KEY" in yaml_text

    def test_has_dvc_step(self):
        w = _load("data_pipeline.yml")
        steps = w["jobs"]["fetch-and-validate"]["steps"]
        step_names = [s.get("name", "") for s in steps]
        assert any("dvc" in n.lower() for n in step_names)

    def test_has_anomaly_detection_step(self):
        yaml_text = (WORKFLOWS_DIR / "data_pipeline.yml").read_text()
        assert "anomaly" in yaml_text.lower()

    def test_has_slack_notification(self):
        yaml_text = (WORKFLOWS_DIR / "data_pipeline.yml").read_text()
        assert "slackapi" in yaml_text or "SLACK_BOT_TOKEN" in yaml_text


# ─── model_training.yml ────────────────────────────────────────────────────────


class TestModelTrainingWorkflow:
    def test_triggers_on_ml_path_changes(self):
        w = _load("model_training.yml")
        push = _triggers(w).get("push", {})
        paths = push.get("paths", [])
        assert any("ml" in p for p in paths)

    def test_has_n_trials_input(self):
        w = _load("model_training.yml")
        inputs = _triggers(w).get("workflow_dispatch", {}).get("inputs", {})
        assert "n_trials" in inputs

    def test_trains_all_three_models(self):
        yaml_text = (WORKFLOWS_DIR / "model_training.yml").read_text()
        assert "confidence_calibrator" in yaml_text
        assert "reward_predictor" in yaml_text
        assert "options_pricer" in yaml_text

    def test_has_threshold_validation_step(self):
        yaml_text = (WORKFLOWS_DIR / "model_training.yml").read_text()
        assert "threshold" in yaml_text.lower()
        # Specific thresholds
        assert "0.60" in yaml_text  # AUC threshold
        assert "0.55" in yaml_text  # F1 threshold

    def test_uploads_model_artifacts(self):
        yaml_text = (WORKFLOWS_DIR / "model_training.yml").read_text()
        assert "upload-artifact" in yaml_text

    def test_mlflow_tracking_uri(self):
        yaml_text = (WORKFLOWS_DIR / "model_training.yml").read_text()
        assert "MLFLOW_TRACKING_URI" in yaml_text

    def test_has_job_summary(self):
        yaml_text = (WORKFLOWS_DIR / "model_training.yml").read_text()
        assert "GITHUB_STEP_SUMMARY" in yaml_text


# ─── bias_detection.yml ───────────────────────────────────────────────────────


class TestBiasDetectionWorkflow:
    def test_triggers_after_model_training(self):
        w = _load("bias_detection.yml")
        workflow_run = _triggers(w).get("workflow_run", {})
        assert "Model Training" in workflow_run.get("workflows", [])

    def test_only_runs_if_training_succeeded(self):
        yaml_text = (WORKFLOWS_DIR / "bias_detection.yml").read_text()
        assert "success" in yaml_text

    def test_checks_all_three_models(self):
        yaml_text = (WORKFLOWS_DIR / "bias_detection.yml").read_text()
        assert "confidence_calibrator" in yaml_text
        assert "reward_predictor" in yaml_text
        assert "options_pricer" in yaml_text

    def test_high_bias_blocks_pipeline(self):
        yaml_text = (WORKFLOWS_DIR / "bias_detection.yml").read_text()
        assert "HIGH" in yaml_text
        # Should exit 1 on HIGH bias
        assert "exit 1" in yaml_text or "sys.exit(1)" in yaml_text

    def test_uploads_bias_reports(self):
        yaml_text = (WORKFLOWS_DIR / "bias_detection.yml").read_text()
        assert "upload-artifact" in yaml_text
        assert "bias-reports" in yaml_text

    def test_has_90_day_retention(self):
        yaml_text = (WORKFLOWS_DIR / "bias_detection.yml").read_text()
        assert "90" in yaml_text  # 90-day retention

    def test_slack_notification_on_block(self):
        yaml_text = (WORKFLOWS_DIR / "bias_detection.yml").read_text()
        assert "SLACK_BOT_TOKEN" in yaml_text


# ─── deploy.yml ───────────────────────────────────────────────────────────────


class TestDeployWorkflow:
    def test_triggers_after_bias_detection(self):
        w = _load("deploy.yml")
        workflow_run = _triggers(w).get("workflow_run", {})
        assert "Bias Detection" in workflow_run.get("workflows", [])

    def test_has_environment_input(self):
        w = _load("deploy.yml")
        inputs = _triggers(w).get("workflow_dispatch", {}).get("inputs", {})
        assert "environment" in inputs
        opts = inputs["environment"].get("options", [])
        assert "staging" in opts
        assert "production" in opts

    def test_has_rollback_input(self):
        w = _load("deploy.yml")
        inputs = _triggers(w).get("workflow_dispatch", {}).get("inputs", {})
        assert "force_rollback" in inputs

    def test_has_docker_build_job(self):
        w = _load("deploy.yml")
        assert any("build" in j.lower() for j in w["jobs"])

    def test_has_promote_models_job(self):
        w = _load("deploy.yml")
        assert any("promote" in j.lower() for j in w["jobs"])

    def test_has_rollback_job(self):
        w = _load("deploy.yml")
        assert any("rollback" in j.lower() for j in w["jobs"])

    def test_has_smoke_tests(self):
        yaml_text = (WORKFLOWS_DIR / "deploy.yml").read_text()
        assert "smoke" in yaml_text.lower()
        assert "/health" in yaml_text

    def test_has_health_check_retry(self):
        yaml_text = (WORKFLOWS_DIR / "deploy.yml").read_text()
        # Should have retry logic
        assert "retry" in yaml_text.lower() or "attempt" in yaml_text.lower()

    def test_railway_token_secret(self):
        yaml_text = (WORKFLOWS_DIR / "deploy.yml").read_text()
        assert "RAILWAY_TOKEN" in yaml_text

    def test_github_container_registry(self):
        yaml_text = (WORKFLOWS_DIR / "deploy.yml").read_text()
        assert "ghcr.io" in yaml_text

    def test_uses_gha_layer_cache(self):
        yaml_text = (WORKFLOWS_DIR / "deploy.yml").read_text()
        assert "type=gha" in yaml_text

    def test_notify_job_runs_on_success_and_failure(self):
        w = _load("deploy.yml")
        assert "notify" in w["jobs"]
        notify_job = w["jobs"]["notify"]
        # Should always run
        assert (
            notify_job.get("if", "").startswith("always()")
            or (WORKFLOWS_DIR / "deploy.yml").read_text().count("Notify") >= 2
        )
