"""Initial migration — create all 9 QuantAgents tables.

Revision ID: 0001
Revises:
Create Date: 2026-03-28
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # analyses
    op.create_table(
        "analyses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("ticker", sa.String(20), nullable=False, index=True),
        sa.Column("user_id", sa.String(100), nullable=False, server_default="default"),
        sa.Column("status", sa.String(50), server_default="pending"),
        sa.Column("recommendation", sa.String(10)),
        sa.Column("confidence", sa.Float),
        sa.Column("debate_rounds", sa.Integer, server_default="0"),
        sa.Column("total_tokens", sa.Integer, server_default="0"),
        sa.Column("latency_ms", sa.Integer),
        sa.Column("error_message", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )

    # agent_reports
    op.create_table(
        "agent_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "analysis_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("analyses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("agent_name", sa.String(100), nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("tools_used", postgresql.JSON),
        sa.Column("confidence", sa.Float),
        sa.Column("tokens_used", sa.Integer, server_default="0"),
        sa.Column("latency_ms", sa.Integer),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # challenges
    op.create_table(
        "challenges",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "analysis_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("analyses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("debate_round", sa.Integer, server_default="1"),
        sa.Column("from_agent", sa.String(100), nullable=False),
        sa.Column("to_agent", sa.String(100), nullable=False),
        sa.Column("question", sa.Text, nullable=False),
        sa.Column("response", sa.Text),
        sa.Column("resolved", sa.Boolean, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
    )

    # trades
    op.create_table(
        "trades",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "analysis_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("analyses.id", ondelete="SET NULL"),
        ),
        sa.Column("ticker", sa.String(20), nullable=False, index=True),
        sa.Column("asset_type", sa.String(20), server_default="stock"),
        sa.Column("side", sa.String(10), nullable=False),
        sa.Column("qty", sa.Float, nullable=False),
        sa.Column("entry_price", sa.Float),
        sa.Column("stop_loss", sa.Float),
        sa.Column("take_profit", sa.Float),
        sa.Column("exit_price", sa.Float),
        sa.Column("pnl", sa.Float),
        sa.Column("pnl_pct", sa.Float),
        sa.Column("status", sa.String(30), server_default="pending"),
        sa.Column("alpaca_order_id", sa.String(100)),
        sa.Column("is_paper", sa.Boolean, server_default="true"),
        sa.Column("options_data", postgresql.JSON),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("filled_at", sa.DateTime(timezone=True)),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
    )

    # trade_reasoning
    op.create_table(
        "trade_reasoning",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "trade_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("trades.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("agent_chain", postgresql.JSON, nullable=False),
        sa.Column("confidence", sa.Float),
        sa.Column("backtest_metrics", postgresql.JSON),
        sa.Column("quantum_weights", postgresql.JSON),
        sa.Column("classical_weights", postgresql.JSON),
        sa.Column("kelly_size", sa.Float),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # reward_signals
    op.create_table(
        "reward_signals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "trade_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("trades.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("check_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("days_elapsed", sa.Integer, nullable=False),
        sa.Column("actual_price", sa.Float),
        sa.Column("predicted_direction", sa.String(10)),
        sa.Column("actual_direction", sa.String(10)),
        sa.Column("actual_return_pct", sa.Float),
        sa.Column("reward_score", sa.Float),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # alerts
    op.create_table(
        "alerts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", sa.String(100), server_default="default"),
        sa.Column("ticker", sa.String(20), nullable=False, index=True),
        sa.Column("alert_type", sa.String(50), nullable=False),
        sa.Column("condition", postgresql.JSON, nullable=False),
        sa.Column("active", sa.Boolean, server_default="true"),
        sa.Column("triggered_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # prompt_versions
    op.create_table(
        "prompt_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("agent_name", sa.String(100), nullable=False, index=True),
        sa.Column("prompt_hash", sa.String(64), nullable=False),
        sa.Column("prompt_content", sa.Text, nullable=False),
        sa.Column("changes_description", sa.Text),
        sa.Column("triggered_by", sa.String(100)),
        sa.Column("accuracy_delta", sa.Float),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
    )

    # model_versions
    op.create_table(
        "model_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("model_name", sa.String(100), nullable=False, index=True),
        sa.Column("version", sa.String(50), nullable=False),
        sa.Column("mlflow_run_id", sa.String(100)),
        sa.Column("metrics", postgresql.JSON),
        sa.Column("bias_check_passed", sa.Boolean),
        sa.Column("bias_report", postgresql.JSON),
        sa.Column("mitigation_applied", sa.Boolean, server_default="false"),
        sa.Column("deployed", sa.Boolean, server_default="false"),
        sa.Column("rolled_back", sa.Boolean, server_default="false"),
        sa.Column("rollback_reason", sa.Text),
        sa.Column("training_data_hash", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()")),
        sa.Column("deployed_at", sa.DateTime(timezone=True)),
    )


def downgrade() -> None:
    op.drop_table("model_versions")
    op.drop_table("prompt_versions")
    op.drop_table("alerts")
    op.drop_table("reward_signals")
    op.drop_table("trade_reasoning")
    op.drop_table("trades")
    op.drop_table("challenges")
    op.drop_table("agent_reports")
    op.drop_table("analyses")
