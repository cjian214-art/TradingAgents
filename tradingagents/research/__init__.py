"""Reproducible, research-only studies for Scanner-style signals.

This package is intentionally separate from the TradingAgents decision graph.
It never submits orders and it does not alter the Scanner's existing scores.
"""

from .market_data import AkShareProvider, OHLCVData, YFinanceProvider
from .study import ScannerStudyConfig, StudyResult, run_scanner_aligned_study

__all__ = [
    "AkShareProvider",
    "OHLCVData",
    "ScannerStudyConfig",
    "StudyResult",
    "YFinanceProvider",
    "run_scanner_aligned_study",
]
