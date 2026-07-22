"""Reproducible, research-only studies for Scanner-style signals.

This package is intentionally separate from the TradingAgents decision graph.
It never submits orders and it does not alter the Scanner's existing scores.
"""

from .ashare_contract import AshareServiceConfig, build_ashare_analysis_request
from .context import build_research_context, load_research_context, render_research_context
from .market_data import AkShareProvider, OHLCVData, YFinanceProvider
from .study import ScannerStudyConfig, StudyResult, run_scanner_aligned_study
from .universe import UniverseStudyConfig, UniverseStudyResult, run_universe_relative_strength_study

__all__ = [
    "AkShareProvider",
    "AshareServiceConfig",
    "build_research_context",
    "build_ashare_analysis_request",
    "load_research_context",
    "OHLCVData",
    "ScannerStudyConfig",
    "StudyResult",
    "UniverseStudyConfig",
    "UniverseStudyResult",
    "YFinanceProvider",
    "run_scanner_aligned_study",
    "run_universe_relative_strength_study",
    "render_research_context",
]
