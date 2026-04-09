"""
QuantAgents — LangGraph State Schema
Forward-compatible TypedDict covering all 8 agents.
Unimplemented agent fields default to None so the graph is composable phase-by-phase.
"""
from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID, uuid4

from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field
from typing_extensions import TypedDict


# ── Sub-models ────────────────────────────────────────────────────────────────

class AgentReport(BaseModel):
    """Output produced by a single research agent."""
    agent_name: str
    content: str
    confidence: float = Field(ge=0.0, le=1.0)
    tools_used: list[str] = Field(default_factory=list)
    tokens_used: int = 0
    latency_ms: int | None = None


class Challenge(BaseModel):
    """Risk Assessor challenge directed at another agent."""
    id: str = Field(default_factory=lambda: str(uuid4()))
    from_agent: str = "risk_assessor"
    to_agent: str
    debate_round: int = 1
    question: str
    response: str | None = None
    resolved: bool = False
    cited_claim: str = ""         # exact claim being challenged
    supporting_evidence: str = "" # evidence from another report


class ScenarioTarget(BaseModel):
    """Bull / base / bear scenario."""
    label: str                          # "bull" | "base" | "bear"
    probability: float = Field(ge=0.0, le=1.0)
    price_target: float | None = None
    return_pct: float | None = None
    catalyst: str = ""


class Catalyst(BaseModel):
    description: str
    date_estimate: str = ""
    impact: str = ""              # "positive" | "negative" | "neutral"


class TradeRecommendation(BaseModel):
    """Final BUY/HOLD/SELL recommendation from Portfolio Strategist."""
    action: str                         # "BUY" | "HOLD" | "SELL"
    confidence: float = Field(ge=0.0, le=1.0)
    entry_price: float | None = None
    stop_loss: float | None = None
    take_profit: float | None = None
    time_horizon: str = "1-3 months"
    scenarios: list[ScenarioTarget] = Field(default_factory=list)
    catalysts: list[Catalyst] = Field(default_factory=list)
    risk_factors: list[str] = Field(default_factory=list)
    reasoning_summary: str = ""


class OptionsLeg(BaseModel):
    """A single options contract leg."""
    action: str                         # "buy" | "sell"
    option_type: str                    # "call" | "put"
    strike: float
    expiry: str                         # YYYY-MM-DD
    contracts: int = 1


class OptionsRecommendation(BaseModel):
    """Options strategy recommendation (Phase 6)."""
    strategy_name: str                      # e.g. "bull_call_spread", "iron_condor", "no_options_trade"
    direction: str = "HOLD"                 # "BUY" | "SELL" | "HOLD"
    iv_rank: float = 50.0                   # IV rank [0-100]
    iv_environment: str = "moderate"        # "low" | "moderate" | "high"
    legs: list[Any] = Field(default_factory=list)  # list of leg dicts or OptionsLeg
    net_debit_per_share: float = 0.0
    net_debit_per_contract: float = 0.0     # net_debit_per_share × 100
    max_profit_per_contract: float | None = None
    max_loss_per_contract: float | None = None
    breakeven: float | None = None
    probability_of_profit: float | None = None
    contracts_suggested: int = 1
    total_cost: float = 0.0
    rationale: str = ""
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    backtest_win_rate: float | None = None
    backtest_avg_return_pct: float | None = None
    # Legacy fields kept for backward compat
    max_loss: float | None = None
    max_gain: float | None = None


class BacktestResult(BaseModel):
    """Output from the Backtest Engine agent."""
    strategy_description: str = ""
    period: str = ""
    win_rate: float | None = None
    loss_rate: float | None = None
    sharpe_ratio: float | None = None
    sortino_ratio: float | None = None
    max_drawdown_pct: float | None = None
    profit_factor: float | None = None
    calmar_ratio: float | None = None
    expectancy_per_trade: float | None = None
    total_trades: int = 0
    validated: bool = False             # True = passes minimum thresholds
    rejection_reason: str | None = None
    monte_carlo_5th_pct: float | None = None
    monte_carlo_95th_pct: float | None = None


class QuantumAllocation(BaseModel):
    """Portfolio allocation from Quantum Optimizer agent."""
    ticker: str
    quantum_weight: float = Field(ge=0.0, le=1.0)
    classical_weight: float = Field(ge=0.0, le=1.0)
    quantum_sharpe: float | None = None
    classical_sharpe: float | None = None
    quantum_var_95: float | None = None
    classical_var_95: float | None = None
    divergence_note: str = ""           # if quantum != classical, explain why


# ── Main State ───────────────────────────────────────────────────────────────

class FinSightState(TypedDict):
    """
    LangGraph state for a single analysis session.
    All agent-specific fields are | None so they can be populated incrementally.
    """
    # ── Input ──────────────────────────────────────────────────────────────
    analysis_id: str
    ticker: str
    user_id: str
    query: str | None                   # optional user override ("focus on earnings")

    # ── Message history (LangGraph managed) ──────────────────────────────
    messages: Annotated[list[BaseMessage], add_messages]

    # ── Memory context (loaded before analysis starts) ────────────────────
    episodic_context: str | None        # Redis: past analyses for this ticker
    semantic_context: str | None        # Qdrant: similar past insights

    # ── Phase 3: Research agent reports ───────────────────────────────────
    market_report: AgentReport | None
    fundamental_report: AgentReport | None
    technical_report: AgentReport | None     # Phase 4

    # ── Phase 4: Debate ────────────────────────────────────────────────────
    challenges: list[Challenge]
    debate_rounds: int
    max_debate_rounds: int

    # ── Phase 4/5: Recommendations ─────────────────────────────────────────
    recommendation: TradeRecommendation | None
    options_recommendation: OptionsRecommendation | None  # Phase 6

    # ── Phase 7: Quantum ───────────────────────────────────────────────────
    quantum_allocations: list[QuantumAllocation]

    # ── Phase 5: Trading ──────────────────────────────────────────────────
    backtest_result: BacktestResult | None
    rl_context: str | None              # RL reward history (past trade accuracy)
    order_placed: bool
    order_id: str | None
    order_details: dict[str, Any] | None

    # ── Control ────────────────────────────────────────────────────────────
    current_phase: str                  # "research" | "debate" | "strategy" | "execution"
    error: str | None


def initial_state(ticker: str, user_id: str = "default", query: str | None = None) -> FinSightState:
    """Create a fresh initial state for a new analysis."""
    import uuid
    return FinSightState(
        analysis_id=str(uuid.uuid4()),
        ticker=ticker.upper().strip(),
        user_id=user_id,
        query=query,
        messages=[],
        episodic_context=None,
        semantic_context=None,
        market_report=None,
        fundamental_report=None,
        technical_report=None,
        challenges=[],
        debate_rounds=0,
        max_debate_rounds=2,
        recommendation=None,
        options_recommendation=None,
        quantum_allocations=[],
        backtest_result=None,
        rl_context=None,
        order_placed=False,
        order_id=None,
        order_details=None,
        current_phase="research",
        error=None,
    )
