from __future__ import annotations

import pandas as pd
import pytest

from tradingagents.research.market_data import normalize_ohlcv
from tradingagents.research.study import (
    ScannerStudyConfig,
    compute_scanner_aligned_signals,
    run_scanner_aligned_study,
)


def _study_frame() -> pd.DataFrame:
    dates = pd.bdate_range("2025-01-02", periods=260)
    close = pd.Series([100.0] * 259 + [110.0])
    return pd.DataFrame(
        {
            "Date": dates,
            "Open": close - 0.5,
            "High": close + 0.5,
            "Low": close - 1.0,
            "Close": close,
            "Volume": [100.0] * 259 + [200.0],
        }
    )


def test_signal_uses_prior_volume_average_and_prior_breakout_high():
    config = ScannerStudyConfig(rsi_min=0, rsi_max=100)
    signals = compute_scanner_aligned_signals(_study_frame(), config)
    last = signals.iloc[-1]
    assert last["volume_average_prior"] == 100.0
    assert last["volume_ratio"] == 2.0
    assert last["prior_high"] == 100.5
    assert bool(last["signal"])


def test_study_rejects_stale_data_before_backtest():
    market_data = normalize_ohlcv(
        _study_frame().iloc[:2],
        provider="fixture",
        symbol="TEST",
        start_date="2025-01-01",
        end_date="2026-07-22",
    )
    with pytest.raises(ValueError, match="stale"):
        run_scanner_aligned_study(market_data)


def test_backtest_returns_reproducible_summary_for_fixture_data():
    pytest.importorskip("backtesting")
    frame = _study_frame()
    market_data = normalize_ohlcv(
        frame,
        provider="fixture",
        symbol="TEST",
        start_date="2025-01-01",
        end_date=frame["Date"].iloc[-1].date().isoformat(),
    )
    result = run_scanner_aligned_study(market_data, ScannerStudyConfig(rsi_min=0, rsi_max=100))
    assert result.summary["study"] == "scanner_aligned_trend_volume_breakout"
    assert result.summary["execution_model"] == "signal on completed close; entry at next available open"
    assert result.summary["signal_count"] >= 1
