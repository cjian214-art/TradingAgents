"""Run a research-only, date-aligned Scanner relative-strength event study."""

from __future__ import annotations

import argparse
from pathlib import Path

from tradingagents.research.market_data import provider_from_name
from tradingagents.research.reporting import write_universe_study_outputs
from tradingagents.research.universe import UniverseStudyConfig, run_universe_relative_strength_study


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=("yfinance", "akshare"), required=True)
    parser.add_argument("--symbols", required=True, help="Comma-separated symbols from one provider.")
    parser.add_argument("--benchmark", required=True, help="A symbol included in --symbols.")
    parser.add_argument("--start", required=True, help="Inclusive date in YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="Inclusive date in YYYY-MM-DD")
    parser.add_argument("--output-dir", type=Path, default=Path("results/universe-research"))
    parser.add_argument("--relative-strength-days", type=int, default=20)
    parser.add_argument("--minimum-percentile", type=float, default=0.8)
    parser.add_argument("--holding-days", default="5,20", help="Comma-separated positive day counts.")
    parser.add_argument("--commission", type=float, default=0.001)
    parser.add_argument("--slippage-bps", type=float, default=5.0)
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    symbols = tuple(symbol.strip().upper() for symbol in args.symbols.split(",") if symbol.strip())
    if len(symbols) < 2:
        raise SystemExit("--symbols must contain at least two symbols.")
    if len(set(symbols)) != len(symbols):
        raise SystemExit("--symbols cannot contain duplicates.")
    provider = provider_from_name(args.provider)
    market_data = {symbol: provider.fetch(symbol, args.start, args.end) for symbol in symbols}
    result = run_universe_relative_strength_study(
        market_data,
        benchmark_symbol=args.benchmark,
        universe_config=UniverseStudyConfig(
            relative_strength_days=args.relative_strength_days,
            minimum_relative_strength_percentile=args.minimum_percentile,
            holding_days=tuple(int(value) for value in args.holding_days.split(",") if value.strip()),
            commission=args.commission,
            slippage_bps=args.slippage_bps,
        ),
    )
    destination = write_universe_study_outputs(result, args.output_dir)
    print(f"Research artifacts written to {destination.resolve()}")
    print(f"Coverage: {result.summary['universe_coverage']['status']}")
    print(f"Qualified events: {result.summary['event_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
