"""
SQLAlchemy ORM Models for QuantAgents
All 9 tables defined here with async support.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


# ─── 1. Analyses ──────────────────────────────────────────────────────────────
class Analysis(Base):
    __tablename__ = "analyses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticker: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(100), nullable=False, default="default")
    status: Mapped[str] = mapped_column(
        String(50), default="pending"
    )  # pending|running|complete|error
    recommendation: Mapped[str | None] = mapped_column(String(10))  # BUY|HOLD|SELL
    confidence: Mapped[float | None] = mapped_column(Float)
    debate_rounds: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    agent_reports: Mapped[list["AgentReport"]] = relationship(back_populates="analysis")
    challenges: Mapped[list["Challenge"]] = relationship(back_populates="analysis")
    trades: Mapped[list["Trade"]] = relationship(back_populates="analysis")


# ─── 2. Agent Reports ─────────────────────────────────────────────────────────
class AgentReport(Base):
    __tablename__ = "agent_reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("analyses.id"), nullable=False)
    agent_name: Mapped[str] = mapped_column(String(100), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tools_used: Mapped[list | None] = mapped_column(JSON)  # list of tool names called
    confidence: Mapped[float | None] = mapped_column(Float)
    tokens_used: Mapped[int] = mapped_column(Integer, default=0)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    analysis: Mapped["Analysis"] = relationship(back_populates="agent_reports")


# ─── 3. Challenges (Debate) ───────────────────────────────────────────────────
class Challenge(Base):
    __tablename__ = "challenges"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("analyses.id"), nullable=False)
    debate_round: Mapped[int] = mapped_column(Integer, default=1)
    from_agent: Mapped[str] = mapped_column(String(100), nullable=False)
    to_agent: Mapped[str] = mapped_column(String(100), nullable=False)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    response: Mapped[str | None] = mapped_column(Text)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    analysis: Mapped["Analysis"] = relationship(back_populates="challenges")


# ─── 4. Trades ────────────────────────────────────────────────────────────────
class Trade(Base):
    __tablename__ = "trades"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("analyses.id"))
    ticker: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    asset_type: Mapped[str] = mapped_column(String(20), default="stock")  # stock|option
    side: Mapped[str] = mapped_column(String(10), nullable=False)  # buy|sell
    qty: Mapped[float] = mapped_column(Float, nullable=False)
    entry_price: Mapped[float | None] = mapped_column(Float)
    stop_loss: Mapped[float | None] = mapped_column(Float)
    take_profit: Mapped[float | None] = mapped_column(Float)
    exit_price: Mapped[float | None] = mapped_column(Float)
    pnl: Mapped[float | None] = mapped_column(Float)
    pnl_pct: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(
        String(30), default="pending"
    )  # pending|filled|cancelled|closed
    alpaca_order_id: Mapped[str | None] = mapped_column(String(100))
    is_paper: Mapped[bool] = mapped_column(Boolean, default=True)
    options_data: Mapped[dict | None] = mapped_column(JSON)  # legs, expiry, strikes, strategy
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    filled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    analysis: Mapped["Analysis | None"] = relationship(back_populates="trades")
    trade_reasoning: Mapped["TradeReasoning | None"] = relationship(back_populates="trade")
    reward_signals: Mapped[list["RewardSignal"]] = relationship(back_populates="trade")


# ─── 5. Trade Reasoning ───────────────────────────────────────────────────────
class TradeReasoning(Base):
    __tablename__ = "trade_reasoning"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trade_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("trades.id"), nullable=False, unique=True
    )
    agent_chain: Mapped[dict] = mapped_column(JSON, nullable=False)  # Full agent report chain
    confidence: Mapped[float | None] = mapped_column(Float)
    backtest_metrics: Mapped[dict | None] = mapped_column(JSON)  # Sharpe, win_rate, drawdown, ...
    quantum_weights: Mapped[dict | None] = mapped_column(JSON)  # quantum allocation
    classical_weights: Mapped[dict | None] = mapped_column(JSON)  # classical allocation
    kelly_size: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    trade: Mapped["Trade"] = relationship(back_populates="trade_reasoning")


# ─── 6. Reward Signals (RL) ───────────────────────────────────────────────────
class RewardSignal(Base):
    __tablename__ = "reward_signals"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    trade_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("trades.id"), nullable=False)
    check_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    days_elapsed: Mapped[int] = mapped_column(Integer, nullable=False)  # 30 | 60 | 90
    actual_price: Mapped[float | None] = mapped_column(Float)
    predicted_direction: Mapped[str | None] = mapped_column(String(10))  # up|down|neutral
    actual_direction: Mapped[str | None] = mapped_column(String(10))
    actual_return_pct: Mapped[float | None] = mapped_column(Float)
    reward_score: Mapped[float | None] = mapped_column(Float)  # -1 to +1
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    trade: Mapped["Trade"] = relationship(back_populates="reward_signals")


# ─── 7. Alerts ────────────────────────────────────────────────────────────────
class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(String(100), default="default")
    ticker: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    alert_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # price|indicator|volume|news|pnl
    condition: Mapped[dict] = mapped_column(
        JSON, nullable=False
    )  # e.g. {"op": ">", "value": 200.0}
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ─── 8. Prompt Versions (RL Feedback) ────────────────────────────────────────
class PromptVersion(Base):
    __tablename__ = "prompt_versions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    prompt_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA-256 of prompt
    prompt_content: Mapped[str] = mapped_column(Text, nullable=False)
    changes_description: Mapped[str | None] = mapped_column(Text)
    triggered_by: Mapped[str | None] = mapped_column(String(100))  # "monthly_retrain"|"manual"
    accuracy_delta: Mapped[float | None] = mapped_column(Float)  # improvement vs prev version
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ─── 9. Model Versions (MLOps) ───────────────────────────────────────────────
class ModelVersion(Base):
    __tablename__ = "model_versions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(50), nullable=False)  # semver e.g. 1.2.0
    mlflow_run_id: Mapped[str | None] = mapped_column(String(100))
    metrics: Mapped[dict | None] = mapped_column(JSON)  # f1, auc, brier_score, ...
    bias_check_passed: Mapped[bool | None] = mapped_column(Boolean)
    bias_report: Mapped[dict | None] = mapped_column(JSON)  # per-slice metrics
    mitigation_applied: Mapped[bool] = mapped_column(Boolean, default=False)
    deployed: Mapped[bool] = mapped_column(Boolean, default=False)
    rolled_back: Mapped[bool] = mapped_column(Boolean, default=False)
    rollback_reason: Mapped[str | None] = mapped_column(Text)
    training_data_hash: Mapped[str | None] = mapped_column(String(64))  # DVC data version
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    deployed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


# ─── 10. Mock Trading Sandbox ────────────────────────────────────────────────
class MockPortfolio(Base):
    __tablename__ = "mock_portfolios"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(
        String(100), nullable=False, unique=True, default="default"
    )
    cash_balance: Mapped[float] = mapped_column(Float, default=100000.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MockPosition(Base):
    __tablename__ = "mock_positions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(String(100), nullable=False, default="default")
    ticker: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    qty: Mapped[float] = mapped_column(Float, default=0.0)
    average_entry_price: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MockTrade(Base):
    __tablename__ = "mock_trades"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(String(100), nullable=False, default="default")
    ticker: Mapped[str] = mapped_column(String(20), nullable=False)
    side: Mapped[str] = mapped_column(String(10), nullable=False)  # BUY / SELL
    qty: Mapped[float] = mapped_column(Float, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)  # qty * price
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
