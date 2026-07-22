"""Narrow, file-based handoff of validated research context to TradingAgents.

The decision graph does not read these files automatically. A caller must
explicitly load and add this context to a report or prompt, which keeps the
experimental study separate from live market-data tools and agent decisions.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .universe import UniverseStudyResult


class ResearchContextError(ValueError):
    """Raised when a persisted research-context file is malformed or unavailable."""


def _safe_symbol_component(symbol: str) -> str:
    cleaned = re.sub(r"[^A-Z0-9._-]+", "_", symbol.upper().strip())
    if not cleaned or cleaned in {".", ".."}:
        raise ResearchContextError("symbol must contain at least one safe filename character.")
    return cleaned


def build_research_context(result: UniverseStudyResult, symbol: str) -> dict[str, Any]:
    """Create schema-versioned, evidence-only context for one universe member."""
    normalized = symbol.upper().strip()
    coverage = result.summary["universe_coverage"]
    if normalized not in coverage["data_quality"]:
        raise ResearchContextError(f"{normalized} is not present in this study universe.")
    events = result.events.loc[result.events["symbol"] == normalized].copy()
    by_holding: dict[str, dict[str, Any]] = {}
    for days, subset in events.groupby("holding_days"):
        by_holding[str(int(days))] = {
            "event_count": int(len(subset)),
            "average_net_return_pct": round(float(subset["net_return"].mean() * 100), 4),
            "average_excess_return_pct": round(float(subset["excess_return"].mean() * 100), 4),
        }
    return {
        "schema_version": "1.0",
        "purpose": "historical research context; not a trading recommendation or live signal",
        "symbol": normalized,
        "study": result.summary["study"],
        "execution_model": result.summary["execution_model"],
        "data_quality": coverage["data_quality"][normalized],
        "universe_coverage": {
            "status": coverage["status"],
            "symbols": coverage["symbols"],
            "common_date_count": coverage["common_date_count"],
            "union_date_count": coverage["union_date_count"],
            "retained_date_ratio": coverage["retained_date_ratio"],
        },
        "cost_model": result.summary["cost_model"],
        "qualified_event_summary": by_holding,
        "latest_qualified_event": (
            events.sort_values("signal_date").iloc[-1].to_dict() if not events.empty else None
        ),
    }


def write_research_contexts(result: UniverseStudyResult, output_dir: str | Path) -> Path:
    """Write one safe, schema-versioned context file per researched symbol."""
    destination = Path(output_dir) / "research_contexts"
    destination.mkdir(parents=True, exist_ok=True)
    for symbol in result.summary["universe_coverage"]["symbols"]:
        context = build_research_context(result, symbol)
        filename = f"{_safe_symbol_component(symbol)}.json"
        (destination / filename).write_text(
            json.dumps(context, ensure_ascii=False, indent=2, default=str) + "\n",
            encoding="utf-8",
        )
    return destination


def load_research_context(output_dir: str | Path, symbol: str) -> dict[str, Any]:
    """Load and minimally validate an explicit context handoff file.

    ``output_dir`` is supplied by the application operator, not an LLM tool
    parameter. The function only reads the expected file below that directory.
    """
    destination = Path(output_dir).resolve() / "research_contexts"
    candidate = (destination / f"{_safe_symbol_component(symbol)}.json").resolve()
    if destination not in candidate.parents:
        raise ResearchContextError("context path escaped its expected output directory.")
    try:
        payload = json.loads(candidate.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ResearchContextError(f"No research context is available for {symbol.upper().strip()}.") from exc
    except json.JSONDecodeError as exc:
        raise ResearchContextError("Research context is not valid JSON.") from exc
    required = {"schema_version", "purpose", "symbol", "data_quality", "universe_coverage"}
    if not isinstance(payload, dict) or not required.issubset(payload):
        raise ResearchContextError("Research context does not match the expected evidence schema.")
    if payload["symbol"] != symbol.upper().strip():
        raise ResearchContextError("Research context symbol does not match the requested symbol.")
    return payload


def render_research_context(context: dict[str, Any]) -> str:
    """Render compact analyst context with explicit limits on its interpretation."""
    quality = context["data_quality"]
    coverage = context["universe_coverage"]
    events = context["qualified_event_summary"]
    latest = context["latest_qualified_event"]
    latest_text = "none" if latest is None else str(latest.get("signal_date", "unknown"))
    event_text = "; ".join(
        f"{days}d: {stats['event_count']} events, avg excess {stats['average_excess_return_pct']}%"
        for days, stats in sorted(events.items(), key=lambda item: int(item[0]))
    ) or "no completed qualified events"
    return (
        "Historical research context only — do not treat as a live signal or recommendation. "
        f"Study: {context['study']}; symbol: {context['symbol']}; source: {quality['provider']}; "
        f"historical data through {quality['latest_date']}; universe coverage: {coverage['status']} "
        f"({coverage['common_date_count']}/{coverage['union_date_count']} shared dates). "
        f"Qualified event evidence: {event_text}; latest qualified historical event: {latest_text}. "
        "Validate any current price, fundamentals, and news with the normal TradingAgents tools."
    )
