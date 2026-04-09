"""
Unit tests for data pipeline scripts.
Uses mocking to avoid external API calls.
"""
from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest


# ─── fetch_prices tests ────────────────────────────────────────────────────────

class TestFetchPrices:
    def _make_price_df(self, ticker="AAPL", rows=5, all_null=False) -> pd.DataFrame:
        dates = pd.date_range("2024-01-01", periods=rows, freq="B")
        data = {
            "Date": dates,
            "Open": [100.0] * rows if not all_null else [np.nan] * rows,
            "High": [105.0] * rows,
            "Low": [99.0] * rows,
            "Close": [102.0] * rows,
            "Volume": [1_000_000] * rows,
        }
        return pd.DataFrame(data)

    @patch("yfinance.download")
    def test_fetch_valid_ticker(self, mock_download, tmp_path):
        os.environ["DATA_DIR"] = str(tmp_path)
        mock_download.return_value = self._make_price_df()

        import importlib, sys
        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        if "fetch_prices" in sys.modules:
            del sys.modules["fetch_prices"]
        import fetch_prices

        from datetime import datetime
        df = fetch_prices.fetch_ticker("AAPL", datetime(2024, 1, 1), datetime(2024, 12, 31))
        assert df is not None
        assert "ticker" in df.columns
        assert len(df) > 0

    @patch("yfinance.download")
    def test_fetch_invalid_ticker_returns_none(self, mock_download, tmp_path):
        mock_download.return_value = pd.DataFrame()  # empty = invalid ticker
        os.environ["DATA_DIR"] = str(tmp_path)

        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        if "fetch_prices" in sys.modules:
            del sys.modules["fetch_prices"]
        import fetch_prices

        from datetime import datetime
        df = fetch_prices.fetch_ticker("INVALID123", datetime(2024, 1, 1), datetime(2024, 12, 31))
        assert df is None


# ─── preprocess tests ─────────────────────────────────────────────────────────

class TestPreprocess:
    def _make_price_df(self, rows: int = 250) -> pd.DataFrame:
        dates = pd.date_range("2023-01-01", periods=rows, freq="B")
        np.random.seed(42)
        close = 100.0 + np.cumsum(np.random.randn(rows) * 0.5)
        return pd.DataFrame({
            "date": dates,
            "open": close * 0.99,
            "high": close * 1.01,
            "low": close * 0.98,
            "close": close,
            "volume": np.random.randint(500_000, 5_000_000, rows),
            "ticker": "TEST",
        })

    def test_rsi_bounds(self):
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        if "preprocess" in sys.modules:
            del sys.modules["preprocess"]
        import preprocess

        df = self._make_price_df(100)
        rsi = preprocess.compute_rsi(df["close"], 14)
        valid = rsi.dropna()
        assert (valid >= 0).all(), "RSI should be >= 0"
        assert (valid <= 100).all(), "RSI should be <= 100"

    def test_macd_calculation(self):
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        if "preprocess" in sys.modules:
            del sys.modules["preprocess"]
        import preprocess

        df = self._make_price_df(100)
        macd, signal, hist = preprocess.compute_macd(df["close"])
        assert len(macd) == len(df), "MACD length must match input"
        # histogram = macd - signal
        diff = (macd - signal - hist).dropna()
        assert (diff.abs() < 1e-10).all(), "histogram = macd - signal"

    def test_add_indicators_columns_created(self):
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        if "preprocess" in sys.modules:
            del sys.modules["preprocess"]
        import preprocess

        df = self._make_price_df(250)
        result = preprocess.add_indicators(df)
        expected_cols = ["rsi_14", "macd", "sma_50", "sma_200", "bb_upper", "atr_14", "volume_ratio"]
        for col in expected_cols:
            assert col in result.columns, f"Expected column: {col}"

    def test_handles_missing_values(self):
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        if "preprocess" in sys.modules:
            del sys.modules["preprocess"]
        import preprocess

        df = self._make_price_df(250)
        # Introduce some NaNs
        df.loc[5:10, "close"] = np.nan
        result = preprocess.add_indicators(df)
        # Should not crash
        assert "rsi_14" in result.columns


# ─── validate_schema tests ─────────────────────────────────────────────────────

class TestValidateSchema:
    def _make_valid_df(self, stale: bool = False) -> pd.DataFrame:
        from datetime import datetime, timedelta
        date = datetime(2020, 1, 1) if stale else datetime.utcnow() - timedelta(days=1)
        dates = pd.date_range(end=date, periods=50, freq="B")
        return pd.DataFrame({
            "date": dates,
            "open": [100.0] * 50,
            "high": [105.0] * 50,
            "low": [98.0] * 50,
            "close": [102.0] * 50,
            "volume": [1_000_000] * 50,
            "ticker": "AAPL",
        })

    def test_valid_data_passes(self):
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        if "validate_schema" in sys.modules:
            del sys.modules["validate_schema"]
        import validate_schema

        df = self._make_valid_df()
        result = validate_schema.validate_price_df(df, "AAPL")
        assert result["passed"] is True
        assert len(result["failures"]) == 0

    def test_null_prices_fail(self):
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        if "validate_schema" in sys.modules:
            del sys.modules["validate_schema"]
        import validate_schema

        df = self._make_valid_df()
        df["close"] = np.nan  # all null
        result = validate_schema.validate_price_df(df, "AAPL")
        assert result["passed"] is False
        assert any("null" in f.lower() for f in result["failures"])

    def test_negative_prices_fail(self):
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        if "validate_schema" in sys.modules:
            del sys.modules["validate_schema"]
        import validate_schema

        df = self._make_valid_df()
        df["close"] = -1.0
        result = validate_schema.validate_price_df(df, "AAPL")
        assert result["passed"] is False

    def test_stale_data_fails(self):
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        if "validate_schema" in sys.modules:
            del sys.modules["validate_schema"]
        import validate_schema

        df = self._make_valid_df(stale=True)
        result = validate_schema.validate_price_df(df, "AAPL")
        assert result["passed"] is False
        assert any("stale" in f.lower() for f in result["failures"])


# ─── detect_anomalies tests ───────────────────────────────────────────────────

class TestDetectAnomalies:
    def _make_price_df(self, rows: int = 60) -> pd.DataFrame:
        from datetime import datetime, timedelta
        dates = pd.date_range(end=datetime.utcnow() - timedelta(days=1), periods=rows, freq="B")
        close = [100.0] * rows
        return pd.DataFrame({
            "date": dates,
            "open": close,
            "high": [c * 1.01 for c in close],
            "low": [c * 0.99 for c in close],
            "close": close,
            "volume": [1_000_000] * rows,
            "ticker": "AAPL",
            "daily_return": [0.0] * rows,
        })

    def test_normal_data_no_anomalies(self):
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        if "detect_anomalies" in sys.modules:
            del sys.modules["detect_anomalies"]
        import detect_anomalies

        df = self._make_price_df(60)
        anomalies = detect_anomalies.detect_price_anomalies(df, "AAPL")
        critical = [a for a in anomalies if a["severity"] == "critical"]
        assert len(critical) == 0

    def test_volume_spike_detected(self):
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        if "detect_anomalies" in sys.modules:
            del sys.modules["detect_anomalies"]
        import detect_anomalies

        df = self._make_price_df(60)
        df.loc[df.index[-1], "volume"] = 50_000_000  # 50× avg
        anomalies = detect_anomalies.detect_price_anomalies(df, "AAPL")
        spikes = [a for a in anomalies if a["type"] == "volume_spike"]
        assert len(spikes) > 0, "5× volume spike should be detected"

    def test_stale_data_critical(self):
        import sys
        sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
        if "detect_anomalies" in sys.modules:
            del sys.modules["detect_anomalies"]
        import detect_anomalies

        df = self._make_price_df(30)
        # Make data stale
        df["date"] = pd.date_range("2023-01-01", periods=30, freq="B")
        anomalies = detect_anomalies.detect_price_anomalies(df, "AAPL")
        stale = [a for a in anomalies if a["type"] == "data_staleness"]
        assert len(stale) > 0, "Stale data should be flagged as critical"
        assert stale[0]["severity"] == "critical"
