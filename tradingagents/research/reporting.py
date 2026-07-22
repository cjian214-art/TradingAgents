"""Write portable, non-sensitive artifacts for a completed research study."""

from __future__ import annotations

import html
import json
from pathlib import Path

import pandas as pd

from .market_data import OHLCVData
from .study import StudyResult


def write_study_outputs(
    market_data: OHLCVData, result: StudyResult, output_dir: str | Path
) -> Path:
    """Create JSON, CSV, Markdown, and HTML artifacts without storing credentials."""
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "summary.json").write_text(
        json.dumps(result.summary, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )
    (destination / "data_quality.json").write_text(
        json.dumps(market_data.quality.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    result.signal_events.to_csv(destination / "signal_events.csv", index=False, encoding="utf-8")
    result.trades.to_csv(destination / "trades.csv", index=False, encoding="utf-8")

    summary_text = json.dumps(result.summary, ensure_ascii=False, indent=2, default=str)
    markdown = "# Scanner-aligned research study\n\n```json\n" + summary_text + "\n```\n"
    (destination / "report.md").write_text(markdown, encoding="utf-8")
    signal_table = result.signal_events.to_html(index=False, escape=True)
    trades_table = result.trades.to_html(index=False, escape=True)
    page = "\n".join(
        [
            "<!doctype html>",
            "<html><head><meta charset=\"utf-8\"><title>Research study</title></head><body>",
            "<h1>Scanner-aligned research study</h1>",
            "<h2>Summary</h2>",
            f"<pre>{html.escape(summary_text)}</pre>",
            "<h2>Signal events</h2>",
            signal_table,
            "<h2>Trades</h2>",
            trades_table,
            "</body></html>",
        ]
    )
    (destination / "report.html").write_text(page, encoding="utf-8")
    return destination
