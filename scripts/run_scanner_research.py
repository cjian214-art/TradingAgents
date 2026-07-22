"""Run one research-only Scanner-aligned study with an explicit data provider."""

from __future__ import annotations

import argparse
from pathlib import Path

from tradingagents.research.market_data import provider_from_name
from tradingagents.research.reporting import write_study_outputs
from tradingagents.research.study import ScannerStudyConfig, run_scanner_aligned_study


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=("yfinance", "akshare"), required=True)
    parser.add_argument("--symbol", required=True, help="For example AAPL, 0700.HK, 600519.SS")
    parser.add_argument("--start", required=True, help="Inclusive date in YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="Inclusive date in YYYY-MM-DD")
    parser.add_argument("--output-dir", type=Path, default=Path("results/research"))
    parser.add_argument("--holding-days", type=int, default=20)
    parser.add_argument("--commission", type=float, default=0.001)
    return parser.parse_args()


def main() -> int:
    args = _arguments()
    provider = provider_from_name(args.provider)
    market_data = provider.fetch(args.symbol, args.start, args.end)
    settings = ScannerStudyConfig(
        holding_days=args.holding_days,
        commission=args.commission,
    )
    result = run_scanner_aligned_study(market_data, settings)
    destination = write_study_outputs(market_data, result, args.output_dir)
    print(f"Research artifacts written to {destination.resolve()}")
    print(f"Signal events: {result.summary['signal_count']}")
    print(f"Completed trades: {result.summary['statistics']['# Trades']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
