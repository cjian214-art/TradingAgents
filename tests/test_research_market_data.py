from __future__ import annotations

import pandas as pd
import pytest

from tradingagents.research.market_data import (
    AkShareProvider,
    ResearchDataError,
    YFinanceProvider,
    normalize_ohlcv,
)


def _frame(start: str = "2026-01-02", periods: int = 12) -> pd.DataFrame:
    dates = pd.bdate_range(start, periods=periods)
    return pd.DataFrame(
        {
            "Date": dates,
            "Open": range(10, 10 + periods),
            "High": range(11, 11 + periods),
            "Low": range(9, 9 + periods),
            "Close": range(10, 10 + periods),
            "Volume": [1_000] * periods,
        }
    )


def test_normalize_drops_future_rows_and_labels_stale_data():
    raw = _frame(periods=2)
    result = normalize_ohlcv(
        raw,
        provider="fixture",
        symbol="AAPL",
        start_date="2026-01-01",
        end_date="2026-01-20",
    )
    assert result.quality.status == "stale"
    assert result.quality.latest_date == "2026-01-05"
    assert result.frame["Date"].max() <= pd.Timestamp("2026-01-20")


def test_akshare_provider_normalizes_chinese_columns_and_symbol():
    seen: dict = {}

    def fetcher(**kwargs):
        seen.update(kwargs)
        return pd.DataFrame(
            {
                "日期": pd.bdate_range("2026-01-02", periods=3),
                "开盘": [10, 11, 12],
                "最高": [11, 12, 13],
                "最低": [9, 10, 11],
                "收盘": [10.5, 11.5, 12.5],
                "成交量": [100, 120, 140],
            }
        )

    result = AkShareProvider(fetcher=fetcher).fetch("600519.SS", "2026-01-01", "2026-01-10")
    assert seen["symbol"] == "600519"
    assert seen["adjust"] == "qfq"
    assert result.quality.provider == "akshare"
    assert list(result.frame.columns) == ["Date", "Open", "High", "Low", "Close", "Volume"]


def test_yfinance_provider_requests_an_inclusive_end_date():
    seen: dict = {}

    def downloader(**kwargs):
        seen.update(kwargs)
        return _frame(periods=3).set_index("Date")

    result = YFinanceProvider(downloader=downloader).fetch("0700.HK", "2026-01-01", "2026-01-06")
    assert seen["end"] == "2026-01-07"
    assert result.quality.market == "HK"


def test_akshare_rejects_non_mainland_symbol():
    with pytest.raises(ResearchDataError, match="six-digit"):
        AkShareProvider(fetcher=lambda **_: _frame()).fetch("AAPL", "2026-01-01", "2026-01-10")
