from __future__ import annotations

from pathlib import Path

from tradingagents.research.context import (
    build_research_context,
    load_research_context,
    render_research_context,
    write_research_contexts,
)
from tradingagents.research.study import ScannerStudyConfig
from tradingagents.research.universe import UniverseStudyConfig, run_universe_relative_strength_study

from .test_research_universe import _data


def _result():
    return run_universe_relative_strength_study(
        {"LEADER": _data("LEADER", 110.0), "PEER": _data("PEER", 101.0), "BENCH": _data("BENCH", 100.0)},
        benchmark_symbol="BENCH",
        signal_config=ScannerStudyConfig(rsi_min=0, rsi_max=100),
        universe_config=UniverseStudyConfig(relative_strength_days=20, holding_days=(5,)),
    )


def test_context_is_evidence_only_and_can_be_loaded_from_its_output_directory(tmp_path: Path):
    result = _result()
    context = build_research_context(result, "LEADER")
    assert context["schema_version"] == "1.0"
    assert "not a trading recommendation" in context["purpose"]
    write_research_contexts(result, tmp_path)
    loaded = load_research_context(tmp_path, "LEADER")
    rendered = render_research_context(loaded)
    assert "Historical research context only" in rendered
    assert "source: fixture" in rendered
