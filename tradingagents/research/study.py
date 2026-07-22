"""No-lookahead Scanner-aligned research study built on backtesting.py."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any

import pandas as pd

from .market_data import REQUIRED_OHLCV_COLUMNS, OHLCVData, ResearchDataError


@dataclass(frozen=True)
class ScannerStudyConfig:
    """Parameters for a research study, never a live-trading configuration."""

    fast_ma_days: int = 50
    slow_ma_days: int = 200
    volume_average_days: int = 50
    volume_ratio_threshold: float = 1.5
    breakout_days: int = 20
    rsi_days: int = 14
    rsi_min: float = 45.0
    rsi_max: float = 75.0
    holding_days: int = 20
    cash: float = 100_000.0
    commission: float = 0.001


@dataclass(frozen=True)
class StudyResult:
    summary: dict[str, Any]
    signal_events: pd.DataFrame
    trades: pd.DataFrame


def _rsi(values: pd.Series, window: int) -> pd.Series:
    changes = values.diff()
    gains = changes.clip(lower=0).rolling(window).mean()
    losses = (-changes.clip(upper=0)).rolling(window).mean()
    relative_strength = gains / losses.replace(0, float("nan"))
    result = 100 - (100 / (1 + relative_strength))
    return result.where(losses != 0, 100.0)


def compute_scanner_aligned_signals(
    frame: pd.DataFrame, config: ScannerStudyConfig | None = None
) -> pd.DataFrame:
    """Compute a transparent trend/volume/breakout signal without future bars.

    The signal captures the Scanner components that are meaningful for a single
    ticker: price above MA50 above MA200, volume expansion against the *prior*
    50 trading days, a close above the prior 20-day high, and a bounded RSI.
    The Scanner's relative-strength rank is intentionally excluded here because
    it requires a date-aligned peer universe, which is a later research stage.
    """
    settings = config or ScannerStudyConfig()
    missing = [column for column in REQUIRED_OHLCV_COLUMNS if column not in frame.columns]
    if missing:
        raise ResearchDataError(f"Cannot calculate study signals; missing {', '.join(missing)}.")

    out = frame.loc[:, list(REQUIRED_OHLCV_COLUMNS)].copy()
    out["Date"] = pd.to_datetime(out["Date"], errors="coerce")
    out = out.dropna(subset=list(REQUIRED_OHLCV_COLUMNS)).sort_values("Date").reset_index(drop=True)
    if out.empty:
        raise ResearchDataError("Cannot calculate study signals from an empty OHLCV frame.")

    out["ma_fast"] = out["Close"].rolling(settings.fast_ma_days).mean()
    out["ma_slow"] = out["Close"].rolling(settings.slow_ma_days).mean()
    out["volume_average_prior"] = (
        out["Volume"].shift(1).rolling(settings.volume_average_days).mean()
    )
    out["volume_ratio"] = out["Volume"] / out["volume_average_prior"]
    out["prior_high"] = out["High"].shift(1).rolling(settings.breakout_days).max()
    out["rsi"] = _rsi(out["Close"], settings.rsi_days)
    out["trend_pass"] = (out["Close"] > out["ma_fast"]) & (out["ma_fast"] > out["ma_slow"])
    out["volume_pass"] = out["volume_ratio"] >= settings.volume_ratio_threshold
    out["breakout_pass"] = out["Close"] > out["prior_high"]
    out["rsi_pass"] = out["rsi"].between(settings.rsi_min, settings.rsi_max, inclusive="both")
    out["signal"] = out["trend_pass"] & out["volume_pass"] & out["breakout_pass"] & out["rsi_pass"]
    return out


def _series_sma(values, window: int):
    return pd.Series(values).rolling(window).mean().to_numpy()


def _series_prior_mean(values, window: int):
    return pd.Series(values).shift(1).rolling(window).mean().to_numpy()


def _series_prior_max(values, window: int):
    return pd.Series(values).shift(1).rolling(window).max().to_numpy()


def _series_rsi(values, window: int):
    return _rsi(pd.Series(values), window).to_numpy()


def _study_strategy(config: ScannerStudyConfig):
    """Create a backtesting.py strategy whose market order enters next-bar open."""
    try:
        from backtesting import Strategy
    except ImportError as exc:  # pragma: no cover - dependency configuration path
        raise ResearchDataError(
            "backtesting.py is not installed. Install the optional 'research' dependency set."
        ) from exc

    class ScannerAlignedStudyStrategy(Strategy):
        def init(self):
            self.fast_ma = self.I(_series_sma, self.data.Close, config.fast_ma_days)
            self.slow_ma = self.I(_series_sma, self.data.Close, config.slow_ma_days)
            self.volume_average = self.I(
                _series_prior_mean, self.data.Volume, config.volume_average_days
            )
            self.prior_high = self.I(_series_prior_max, self.data.High, config.breakout_days)
            self.rsi = self.I(_series_rsi, self.data.Close, config.rsi_days)
            self.entry_bar: int | None = None

        def next(self):
            close = self.data.Close[-1]
            volume_ratio = self.data.Volume[-1] / self.volume_average[-1]
            eligible = (
                pd.notna(self.fast_ma[-1])
                and pd.notna(self.slow_ma[-1])
                and pd.notna(volume_ratio)
                and pd.notna(self.prior_high[-1])
                and pd.notna(self.rsi[-1])
                and close > self.fast_ma[-1] > self.slow_ma[-1]
                and volume_ratio >= config.volume_ratio_threshold
                and close > self.prior_high[-1]
                and config.rsi_min <= self.rsi[-1] <= config.rsi_max
            )
            if not self.position and eligible:
                self.buy()
                self.entry_bar = len(self.data)
            elif self.position and self.entry_bar is not None:
                if len(self.data) - self.entry_bar >= config.holding_days:
                    self.position.close()
                    self.entry_bar = None

    return ScannerAlignedStudyStrategy


def _safe_stat(value: Any) -> Any:
    if isinstance(value, (int, str, bool)) or value is None:
        return value
    if isinstance(value, float):
        return None if math.isnan(value) else round(value, 4)
    if hasattr(value, "item"):
        return _safe_stat(value.item())
    return str(value)


def run_scanner_aligned_study(
    market_data: OHLCVData, config: ScannerStudyConfig | None = None
) -> StudyResult:
    """Run a reproducible research study and return only analysis artifacts.

    Signals are formed on a completed daily bar and submitted as ordinary
    backtesting.py market orders, which execute at the following bar's open.
    This intentionally prevents same-close fills and look-ahead bias.
    """
    settings = config or ScannerStudyConfig()
    if market_data.quality.status != "ok":
        raise ResearchDataError(
            f"Refusing to study stale data: latest bar is {market_data.quality.latest_date} "
            f"for requested end {market_data.quality.requested_end}."
        )
    signals = compute_scanner_aligned_signals(market_data.frame, settings)
    try:
        from backtesting import Backtest
    except ImportError as exc:  # pragma: no cover - dependency configuration path
        raise ResearchDataError(
            "backtesting.py is not installed. Install the optional 'research' dependency set."
        ) from exc

    input_frame = signals.loc[:, list(REQUIRED_OHLCV_COLUMNS)].copy().set_index("Date")
    strategy = _study_strategy(settings)
    backtest = Backtest(
        input_frame,
        strategy,
        cash=settings.cash,
        commission=settings.commission,
        exclusive_orders=True,
    )
    stats = backtest.run()
    summary_keys = (
        "Start",
        "End",
        "Duration",
        "Exposure Time [%]",
        "Equity Final [$]",
        "Return [%]",
        "Buy & Hold Return [%]",
        "Max. Drawdown [%]",
        "# Trades",
        "Win Rate [%]",
        "Sharpe Ratio",
    )
    summary = {
        "study": "scanner_aligned_trend_volume_breakout",
        "data_quality": market_data.quality.to_dict(),
        "config": asdict(settings),
        "signal_count": int(signals["signal"].sum()),
        "execution_model": "signal on completed close; entry at next available open",
        "relative_strength": "not evaluated: requires a date-aligned peer universe",
        "statistics": {key: _safe_stat(stats.get(key)) for key in summary_keys},
    }
    trades = stats.get("_trades", pd.DataFrame()).copy()
    signal_events = signals.loc[signals["signal"]].copy()
    return StudyResult(summary=summary, signal_events=signal_events, trades=trades)
