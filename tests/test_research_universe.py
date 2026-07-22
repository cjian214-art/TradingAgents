from __future__ import annotations

import pandas as pd

from tradingagents.research.market_data import normalize_ohlcv
from tradingagents.research.study import ScannerStudyConfig
from tradingagents.research.universe import (
    UniverseStudyConfig,
    align_universe,
    run_universe_relative_strength_study,
)


def _frame(final_close: float, *, drop_date: bool = False) -> pd.DataFrame:
    dates = pd.bdate_range("2024-01-02", periods=286)
    closes = [100.0] * 259 + [final_close] + [final_close + 1.0] * 26
    frame = pd.DataFrame(
        {
            "Date": dates,
            "Open": [99.5] * 259 + [final_close - 0.5] + [final_close + 0.5] * 26,
            "High": [100.5] * 259 + [final_close + 0.5] + [final_close + 1.5] * 26,
            "Low": [99.0] * 286,
            "Close": closes,
            "Volume": [100.0] * 259 + [200.0] + [100.0] * 26,
        }
    )
    return frame.drop(index=150).reset_index(drop=True) if drop_date else frame


def _data(symbol: str, final_close: float, *, drop_date: bool = False):
    frame = _frame(final_close, drop_date=drop_date)
    return normalize_ohlcv(
        frame,
        provider="fixture",
        symbol=symbol,
        start_date="2024-01-02",
        end_date="2025-02-04",
    )


def test_relative_strength_events_use_aligned_universe_and_next_session_entry():
    data = {
        "LEADER": _data("LEADER", 110.0),
        "PEER": _data("PEER", 101.0),
        "BENCH": _data("BENCH", 100.0),
    }
    result = run_universe_relative_strength_study(
        data,
        benchmark_symbol="BENCH",
        signal_config=ScannerStudyConfig(rsi_min=0, rsi_max=100),
        universe_config=UniverseStudyConfig(relative_strength_days=20, holding_days=(5, 20)),
    )
    assert result.summary["universe_coverage"]["status"] == "complete"
    assert result.summary["event_count"] >= 2
    leader_events = result.events.loc[result.events["symbol"] == "LEADER"]
    assert not leader_events.empty
    event = leader_events.iloc[0]
    assert event["relative_strength_rank"] == 1
    assert event["relative_strength_percentile"] == 1.0
    assert pd.Timestamp(event["entry_date"]) > pd.Timestamp(event["signal_date"])
    assert result.summary["holding_period_summaries"]["5"]["event_count"] >= 1


def test_universe_reports_reduced_coverage_without_filling_peer_prices():
    aligned = align_universe(
        {
            "LEADER": _data("LEADER", 110.0),
            "PEER": _data("PEER", 101.0, drop_date=True),
            "BENCH": _data("BENCH", 100.0),
        }
    )
    assert aligned.coverage_status == "reduced"
    assert aligned.retained_date_ratio < 1.0
    assert len(aligned.common_dates) == 285
    assert len(aligned.frames["PEER"]) == 285
