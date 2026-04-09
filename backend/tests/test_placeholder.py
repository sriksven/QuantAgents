"""
Backend test placeholder — verifies the test infrastructure works.
Real tests will be added per phase.
"""
import pytest


def test_placeholder():
    """Placeholder that always passes — real tests added per phase."""
    assert True


def test_config_loads():
    """Verify settings load from defaults without real env vars."""
    import os
    # Set dummy values so pydantic-settings doesn't raise
    os.environ.setdefault("OPENAI_API_KEY", "test")
    os.environ.setdefault("TAVILY_API_KEY", "test")
    os.environ.setdefault("ALPHA_VANTAGE_API_KEY", "test")
    os.environ.setdefault("ALPACA_API_KEY", "test")
    os.environ.setdefault("ALPACA_SECRET_KEY", "test")

    import sys
    sys.path.insert(0, ".")
    from config import Settings
    s = Settings()
    assert s.openai_model == "gpt-4o"
    assert s.alpaca_paper is True
    assert s.enable_live_trading is False
