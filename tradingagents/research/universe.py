"""Date-aligned peer-universe research for Scanner-style relative strength.

This module is deliberately an event study, rather than a portfolio allocator.
It measures what happened after qualified signals across a supplied universe and
retains the data-coverage evidence needed to interpret those results.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from functools import reduce
from typing import Any, Mapping

import pandas as pd

from .market_data import OHLCVData, REQUIRED_OHLCV_COLUMNS, ResearchDataError
from .study import ScannerStudyConfig, compute_scanner_aligned_signals


@dataclass(frozen=True)
class UniverseStudyConfig:
    """Fixed assumptions for a research-only relative-strength event study."""

    relative_strength_days: int = 20
    minimum_relative_strength_percentile: float = 0.8
    holding_days: tuple[int, ...] = (5, 20)
    commission: float = 0.001
    slippage_bps: float = 5.0


@dataclass(frozen=True)
class AlignedUniverse:
    """OHLCV frames restricted to dates all supplied symbols share."""

    frames: dict[str, pd.DataFrame]
    quality: dict[str, dict[str, Any]]
    common_dates: pd.DatetimeIndex
    union_date_count: int
    retained_date_ratio: float
    symbol_coverage_ratio: dict[str, float]
    coverage_status: str


@dataclass(frozen=True)
class UniverseStudyResult:
    summary: dict[str, Any]
    rankings: pd.DataFrame
    events: pd.DataFrame


def _validate_config(config: UniverseStudyConfig) -> None:
    if config.relative_strength_days < 1:
        raise ValueError("relative_strength_days must be at least 1.")
    if not 0 < config.minimum_relative_strength_percentile <= 1:
        raise ValueError("minimum_relative_strength_percentile must be in (0, 1].")
    if not config.holding_days or any(days < 1 for days in config.holding_days):
        raise ValueError("holding_days must contain one or more positive day counts.")
    if config.commission < 0 or config.slippage_bps < 0:
        raise ValueError("commission and slippage_bps cannot be negative.")


def align_universe(market_data: Mapping[str, OHLCVData]) -> AlignedUniverse:
    """Intersect dates across a universe without filling missing peer prices.

    Rankings are only calculated on exact shared dates. The returned coverage
    values make any lost dates explicit, rather than implying a complete market
    universe when a provider supplied only partial history.
    """
    if len(market_data) < 2:
        raise ResearchDataError("Relative-strength research needs at least two symbols.")

    indexed_frames: dict[str, pd.DataFrame] = {}
    quality: dict[str, dict[str, Any]] = {}
    date_sets: list[pd.DatetimeIndex] = []
    for raw_symbol, data in market_data.items():
        symbol = raw_symbol.upper().strip()
        if not symbol or symbol in indexed_frames:
            raise ResearchDataError("Universe symbols must be non-empty and unique.")
        if data.quality.status != "ok":
            raise ResearchDataError(f"Refusing partial universe: {symbol} data is stale.")
        frame = data.frame.loc[:, list(REQUIRED_OHLCV_COLUMNS)].copy()
        frame["Date"] = pd.to_datetime(frame["Date"], errors="coerce")
        frame = frame.dropna(subset=list(REQUIRED_OHLCV_COLUMNS)).drop_duplicates("Date", keep="last")
        frame = frame.sort_values("Date").set_index("Date")
        if frame.empty:
            raise ResearchDataError(f"Refusing partial universe: {symbol} has no usable rows.")
        indexed_frames[symbol] = frame
        quality[symbol] = data.quality.to_dict()
        date_sets.append(pd.DatetimeIndex(frame.index))

    common_dates = reduce(lambda left, right: left.intersection(right), date_sets).sort_values()
    union_dates = reduce(lambda left, right: left.union(right), date_sets).sort_values()
    if common_dates.empty:
        raise ResearchDataError("Universe symbols do not share any usable trading dates.")
    union_count = len(union_dates)
    coverage = {
        symbol: round(len(frame.index.intersection(union_dates)) / union_count, 6)
        for symbol, frame in indexed_frames.items()
    }
    retained = round(len(common_dates) / union_count, 6)
    return AlignedUniverse(
        frames={symbol: frame.reindex(common_dates).reset_index() for symbol, frame in indexed_frames.items()},
        quality=quality,
        common_dates=common_dates,
        union_date_count=union_count,
        retained_date_ratio=retained,
        symbol_coverage_ratio=coverage,
        coverage_status="complete" if retained == 1.0 else "reduced",
    )


def compute_relative_strength_rankings(
    aligned: AlignedUniverse, relative_strength_days: int
) -> pd.DataFrame:
    """Return one date-aligned cross-sectional ranking table per completed bar."""
    close = pd.DataFrame(
        {symbol: frame.set_index("Date")["Close"] for symbol, frame in aligned.frames.items()}
    ).sort_index()
    returns = close.pct_change(periods=relative_strength_days, fill_method=None)
    ranks = returns.rank(axis=1, ascending=False, method="min")
    valid_counts = returns.notna().sum(axis=1)
    percentiles = ranks.rsub(valid_counts, axis=0).add(1).div(valid_counts, axis=0)

    records: list[pd.DataFrame] = []
    for symbol in close.columns:
        records.append(
            pd.DataFrame(
                {
                    "Date": close.index,
                    "symbol": symbol,
                    "relative_return": returns[symbol].to_numpy(),
                    "relative_strength_rank": ranks[symbol].to_numpy(),
                    "relative_strength_percentile": percentiles[symbol].to_numpy(),
                }
            )
        )
    return pd.concat(records, ignore_index=True).sort_values(["Date", "symbol"]).reset_index(drop=True)


def _summary_for_holding(events: pd.DataFrame, holding_days: int) -> dict[str, Any]:
    subset = events.loc[events["holding_days"] == holding_days]
    if subset.empty:
        return {
            "event_count": 0,
            "average_net_return_pct": None,
            "median_net_return_pct": None,
            "win_rate_pct": None,
            "average_benchmark_return_pct": None,
            "average_excess_return_pct": None,
        }
    return {
        "event_count": int(len(subset)),
        "average_net_return_pct": round(float(subset["net_return"].mean() * 100), 4),
        "median_net_return_pct": round(float(subset["net_return"].median() * 100), 4),
        "win_rate_pct": round(float((subset["net_return"] > 0).mean() * 100), 4),
        "average_benchmark_return_pct": round(float(subset["benchmark_net_return"].mean() * 100), 4),
        "average_excess_return_pct": round(float(subset["excess_return"].mean() * 100), 4),
    }


def run_universe_relative_strength_study(
    market_data: Mapping[str, OHLCVData],
    *,
    benchmark_symbol: str,
    signal_config: ScannerStudyConfig | None = None,
    universe_config: UniverseStudyConfig | None = None,
) -> UniverseStudyResult:
    """Measure post-signal outcomes for qualified, high-RS Scanner events.

    A signal is formed on a completed close. Each event enters at the following
    shared-session open and exits at the stated holding-period close. Results
    are independent event observations, not a claim of an investable portfolio.
    """
    settings = universe_config or UniverseStudyConfig()
    _validate_config(settings)
    aligned = align_universe(market_data)
    benchmark = benchmark_symbol.upper().strip()
    if benchmark not in aligned.frames:
        raise ResearchDataError("benchmark_symbol must be included in the supplied universe.")

    rankings = compute_relative_strength_rankings(aligned, settings.relative_strength_days)
    ranking_index = rankings.set_index(["Date", "symbol"])
    scanner_settings = signal_config or ScannerStudyConfig()
    event_rows: list[dict[str, Any]] = []
    cost_per_side = scanner_settings.commission + settings.slippage_bps / 10_000
    round_trip_cost = cost_per_side * 2
    benchmark_frame = aligned.frames[benchmark].set_index("Date")

    for symbol, frame in aligned.frames.items():
        signals = compute_scanner_aligned_signals(frame, scanner_settings).set_index("Date")
        for position, (signal_date, row) in enumerate(signals.iterrows()):
            ranking = ranking_index.loc[(signal_date, symbol)]
            qualified = bool(row["signal"]) and pd.notna(ranking["relative_strength_percentile"])
            if not qualified or ranking["relative_strength_percentile"] < settings.minimum_relative_strength_percentile:
                continue
            for holding_days in settings.holding_days:
                exit_position = position + holding_days
                if exit_position >= len(signals):
                    continue
                entry_position = position + 1
                entry_date = signals.index[entry_position]
                exit_date = signals.index[exit_position]
                entry_open = float(signals.iloc[entry_position]["Open"])
                exit_close = float(signals.iloc[exit_position]["Close"])
                benchmark_entry = float(benchmark_frame.loc[entry_date, "Open"])
                benchmark_exit = float(benchmark_frame.loc[exit_date, "Close"])
                gross_return = exit_close / entry_open - 1
                benchmark_gross_return = benchmark_exit / benchmark_entry - 1
                net_return = gross_return - round_trip_cost
                benchmark_net_return = benchmark_gross_return - round_trip_cost
                event_rows.append(
                    {
                        "symbol": symbol,
                        "signal_date": signal_date.date().isoformat(),
                        "entry_date": entry_date.date().isoformat(),
                        "exit_date": exit_date.date().isoformat(),
                        "holding_days": holding_days,
                        "relative_return": float(ranking["relative_return"]),
                        "relative_strength_rank": int(ranking["relative_strength_rank"]),
                        "relative_strength_percentile": float(ranking["relative_strength_percentile"]),
                        "entry_open": entry_open,
                        "exit_close": exit_close,
                        "gross_return": gross_return,
                        "net_return": net_return,
                        "benchmark_symbol": benchmark,
                        "benchmark_gross_return": benchmark_gross_return,
                        "benchmark_net_return": benchmark_net_return,
                        "excess_return": net_return - benchmark_net_return,
                    }
                )

    event_columns = (
        "symbol", "signal_date", "entry_date", "exit_date", "holding_days", "relative_return",
        "relative_strength_rank", "relative_strength_percentile", "entry_open", "exit_close",
        "gross_return", "net_return", "benchmark_symbol", "benchmark_gross_return",
        "benchmark_net_return", "excess_return",
    )
    events = pd.DataFrame(event_rows, columns=event_columns).sort_values(
        ["signal_date", "symbol", "holding_days"]
    ).reset_index(drop=True)
    summary = {
        "study": "scanner_relative_strength_event_study",
        "method": "date-aligned cross-sectional event study; not a portfolio simulation",
        "benchmark_symbol": benchmark,
        "signal_config": asdict(scanner_settings),
        "universe_config": {**asdict(settings), "holding_days": list(settings.holding_days)},
        "execution_model": "signal on completed close; entry at next shared-session open",
        "cost_model": {
            "commission_per_side": scanner_settings.commission,
            "slippage_bps_per_side": settings.slippage_bps,
            "round_trip_cost_fraction": round_trip_cost,
        },
        "universe_coverage": {
            "symbols": sorted(aligned.frames),
            "common_date_count": len(aligned.common_dates),
            "union_date_count": aligned.union_date_count,
            "retained_date_ratio": aligned.retained_date_ratio,
            "symbol_coverage_ratio": aligned.symbol_coverage_ratio,
            "status": aligned.coverage_status,
            "data_quality": aligned.quality,
        },
        "event_count": int(len(events)),
        "holding_period_summaries": {
            str(days): _summary_for_holding(events, days) for days in settings.holding_days
        },
    }
    return UniverseStudyResult(summary=summary, rankings=rankings, events=events)
