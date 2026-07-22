"""Write portable, non-sensitive artifacts for a completed research study."""

from __future__ import annotations

import html
import json
from pathlib import Path

from .context import write_research_contexts
from .market_data import OHLCVData
from .study import StudyResult
from .universe import UniverseStudyResult


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


def write_universe_study_outputs(result: UniverseStudyResult, output_dir: str | Path) -> Path:
    """Write transparent coverage, ranking, and event-study artifacts."""
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    summary_text = json.dumps(result.summary, ensure_ascii=False, indent=2, default=str)
    (destination / "summary.json").write_text(summary_text + "\n", encoding="utf-8")
    result.rankings.to_csv(destination / "relative_strength_rankings.csv", index=False, encoding="utf-8")
    result.events.to_csv(destination / "qualified_events.csv", index=False, encoding="utf-8")
    write_research_contexts(result, destination)
    markdown = "# Date-aligned relative-strength event study\n\n```json\n" + summary_text + "\n```\n"
    (destination / "report.md").write_text(markdown, encoding="utf-8")
    page = "\n".join(
        [
            "<!doctype html>",
            "<html><head><meta charset=\"utf-8\"><title>Relative-strength research</title></head><body>",
            "<h1>Date-aligned relative-strength event study</h1>",
            "<h2>Summary</h2>",
            f"<pre>{html.escape(summary_text)}</pre>",
            "<h2>Qualified events</h2>",
            result.events.to_html(index=False, escape=True),
            "</body></html>",
        ]
    )
    (destination / "report.html").write_text(page, encoding="utf-8")
    return destination
