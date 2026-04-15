"""
QuantAgents — Configuration
Loaded from environment variables using pydantic-settings.
"""

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── LLM ──────────────────────────────────────────────────
    openai_api_key: str = Field(..., description="OpenAI API key")
    openai_model: str = "gpt-4o"
    openai_mini_model: str = "gpt-4o-mini"

    # ── Alpaca Broker ─────────────────────────────────────────
    alpaca_api_key: str = Field(..., description="Alpaca API key")
    alpaca_secret_key: str = Field(..., description="Alpaca secret key")
    alpaca_paper: bool = True
    alpaca_base_url: str = "https://paper-api.alpaca.markets"

    # ── Data APIs ─────────────────────────────────────────────
    tavily_api_key: str = Field(..., description="Tavily search API key")
    alpha_vantage_api_key: str = Field(..., description="Alpha Vantage API key")

    # ── PostgreSQL ────────────────────────────────────────────
    database_url: str = Field(
        "postgresql+asyncpg://quantagents:quantagents_secret@localhost:5432/quantagents"
    )

    # ── Redis ─────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"

    # ── Qdrant ───────────────────────────────────────────────
    qdrant_url: str = "http://localhost:6333"
    qdrant_collection: str = "quantagents_knowledge"

    # ── Langfuse ─────────────────────────────────────────────
    langfuse_host: str = "http://localhost:3001"
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""

    # ── MLflow ───────────────────────────────────────────────
    mlflow_tracking_uri: str = "http://localhost:5001"
    mlflow_experiment_name: str = "quantagents"

    # ── Backend ──────────────────────────────────────────────
    backend_port: int = 8000
    cors_origins: str = "http://localhost:3000,http://localhost:8000"

    # ── Feature Flags ─────────────────────────────────────────
    enable_quantum: bool = True
    enable_live_trading: bool = False
    max_debate_rounds: int = 2
    kelly_fraction: float = Field(0.5, ge=0.1, le=1.0)
    backtest_sharpe_threshold: float = Field(1.0, ge=0.0)
    confidence_threshold: float = Field(0.65, ge=0.0, le=1.0)
    max_position_pct: float = Field(0.30, ge=0.0, le=1.0)
    max_daily_loss_pct: float = Field(0.05, ge=0.0, le=1.0)

    # ── Notifications ─────────────────────────────────────────
    slack_webhook_url: str = ""

    @field_validator("kelly_fraction", "confidence_threshold", mode="before")
    @classmethod
    def validate_fraction(cls, v: float) -> float:
        if not (0.0 <= float(v) <= 1.0):
            raise ValueError("Must be between 0 and 1")
        return float(v)

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    @property
    def is_paper_trading(self) -> bool:
        return self.alpaca_paper or not self.enable_live_trading


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance — import this everywhere."""
    return Settings()  # type: ignore[call-arg]
