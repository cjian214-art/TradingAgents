"""Normalized OHLCV inputs and data-quality labels for research studies.

The existing TradingAgents data-flow remains the source for agent reports. This
module serves the separate, reproducible research path: each returned frame
states its provider, requested period, latest usable bar, and freshness status.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import timedelta
from typing import Literal

import pandas as pd

QualityStatus = Literal["ok", "stale"]
REQUIRED_OHLCV_COLUMNS = ("Date", "Open", "High", "Low", "Close", "Volume")


class ResearchDataError(ValueError):
    """Raised when a research provider cannot produce a usable OHLCV frame."""


@dataclass(frozen=True)
class DataQuality:
    provider: str
    symbol: str
    market: str
    requested_start: str
    requested_end: str
    latest_date: str
    row_count: int
    status: QualityStatus
    freshness_days: int

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class OHLCVData:
    frame: pd.DataFrame
    quality: DataQuality


def infer_market(symbol: str) -> str:
    """Classify the small market set supported by the initial provider layer."""
    upper = symbol.upper().strip()
    if upper.endswith((".SS", ".SZ", ".BJ")):
        return "CN"
    if upper.endswith(".HK"):
        return "HK"
    return "US"


def normalize_ohlcv(
    raw: pd.DataFrame,
    *,
    provider: str,
    symbol: str,
    start_date: str,
    end_date: str,
    market: str | None = None,
    max_stale_days: int = 10,
) -> OHLCVData:
    """Normalize a provider frame, enforce the requested date boundary, label freshness.

    Rows later than ``end_date`` are removed before a study can access them. A
    stale frame is returned with a visible label so callers can choose to stop
    rather than silently treating old prices as current.
    """
    if raw is None or raw.empty:
        raise ResearchDataError(f"{provider} returned no OHLCV rows for {symbol}.")

    frame = raw.copy()
    if isinstance(frame.index, pd.DatetimeIndex):
        frame = frame.reset_index()

    aliases = {
        "date": "Date",
        "日期": "Date",
        "open": "Open",
        "开盘": "Open",
        "high": "High",
        "最高": "High",
        "low": "Low",
        "最低": "Low",
        "close": "Close",
        "收盘": "Close",
        "volume": "Volume",
        "成交量": "Volume",
    }
    rename_map = {
        column: aliases.get(str(column).strip().lower(), aliases.get(str(column).strip(), column))
        for column in frame.columns
    }
    frame = frame.rename(columns=rename_map)

    missing = [column for column in REQUIRED_OHLCV_COLUMNS if column not in frame.columns]
    if missing:
        raise ResearchDataError(
            f"{provider} data for {symbol} is missing required columns: {', '.join(missing)}."
        )

    frame = frame.loc[:, list(REQUIRED_OHLCV_COLUMNS)].copy()
    frame["Date"] = pd.to_datetime(frame["Date"], errors="coerce").dt.tz_localize(None)
    for column in REQUIRED_OHLCV_COLUMNS[1:]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=list(REQUIRED_OHLCV_COLUMNS))
    frame = frame[(frame["Date"] >= pd.Timestamp(start_date)) & (frame["Date"] <= pd.Timestamp(end_date))]
    frame = frame.drop_duplicates(subset=["Date"], keep="last").sort_values("Date").reset_index(drop=True)
    if frame.empty:
        raise ResearchDataError(
            f"{provider} returned no usable rows for {symbol} within {start_date} to {end_date}."
        )

    latest = pd.Timestamp(frame["Date"].iloc[-1]).normalize()
    requested_end = pd.Timestamp(end_date).normalize()
    freshness_days = max(0, (requested_end - latest).days)
    status: QualityStatus = "stale" if freshness_days > max_stale_days else "ok"
    quality = DataQuality(
        provider=provider,
        symbol=symbol.upper(),
        market=market or infer_market(symbol),
        requested_start=pd.Timestamp(start_date).date().isoformat(),
        requested_end=requested_end.date().isoformat(),
        latest_date=latest.date().isoformat(),
        row_count=len(frame),
        status=status,
        freshness_days=freshness_days,
    )
    return OHLCVData(frame=frame, quality=quality)


class YFinanceProvider:
    """Research-only Yahoo provider for US and Hong Kong daily OHLCV."""

    name = "yfinance"

    def __init__(self, downloader: Callable[..., pd.DataFrame] | None = None):
        self._downloader = downloader

    def fetch(self, symbol: str, start_date: str, end_date: str) -> OHLCVData:
        end_inclusive = (pd.Timestamp(end_date) + timedelta(days=1)).strftime("%Y-%m-%d")
        if self._downloader is None:
            try:
                import yfinance as yf
            except ImportError as exc:  # pragma: no cover - dependency configuration path
                raise ResearchDataError("yfinance is not installed.") from exc
            raw = yf.download(
                symbol,
                start=start_date,
                end=end_inclusive,
                auto_adjust=False,
                multi_level_index=False,
                progress=False,
            )
        else:
            raw = self._downloader(symbol=symbol, start=start_date, end=end_inclusive)
        return normalize_ohlcv(
            raw,
            provider=self.name,
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
        )


class AkShareProvider:
    """Research-only AKShare provider for mainland and Beijing A-share symbols."""

    name = "akshare"
    _CN_SYMBOL = re.compile(r"^(?P<code>\d{6})(?:\.(?:SS|SZ|BJ))?$")

    def __init__(self, fetcher: Callable[..., pd.DataFrame] | None = None):
        self._fetcher = fetcher

    @classmethod
    def _code(cls, symbol: str) -> str:
        match = cls._CN_SYMBOL.match(symbol.upper().strip())
        if not match:
            raise ResearchDataError(
                "AKShare research currently expects a six-digit mainland/Beijing symbol, "
                "for example 600519.SS, 000001.SZ, or 920000.BJ."
            )
        return match.group("code")

    def fetch(self, symbol: str, start_date: str, end_date: str) -> OHLCVData:
        code = self._code(symbol)
        if self._fetcher is None:
            try:
                import akshare as ak
            except ImportError as exc:  # pragma: no cover - dependency configuration path
                raise ResearchDataError(
                    "AKShare is not installed. Install the optional 'research' dependency set."
                ) from exc
            fetcher = ak.stock_zh_a_hist
        else:
            fetcher = self._fetcher
        raw = fetcher(
            symbol=code,
            period="daily",
            start_date=pd.Timestamp(start_date).strftime("%Y%m%d"),
            end_date=pd.Timestamp(end_date).strftime("%Y%m%d"),
            adjust="qfq",
        )
        return normalize_ohlcv(
            raw,
            provider=self.name,
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
            market="CN",
        )


def provider_from_name(name: str) -> YFinanceProvider | AkShareProvider:
    """Return an explicit provider; no implicit cross-source fallback occurs."""
    normalized = name.strip().lower()
    if normalized == "yfinance":
        return YFinanceProvider()
    if normalized == "akshare":
        return AkShareProvider()
    raise ValueError("provider must be one of: yfinance, akshare")
