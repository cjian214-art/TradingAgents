from __future__ import annotations

import pytest

from tradingagents.research.ashare_contract import (
    AshareContractError,
    AshareServiceConfig,
    build_ashare_analysis_request,
    normalize_ashare_symbol,
    validate_ashare_job_response,
)


def test_contract_normalizes_symbols_and_builds_a_non_executing_request():
    assert normalize_ashare_symbol("600519.SS") == "600519.SH"
    assert normalize_ashare_symbol("000001.SZ") == "000001.SZ"
    assert normalize_ashare_symbol("920000.BJ") == "920000.BJ"
    request = build_ashare_analysis_request("600519.SS", "2026-07-22")
    assert request["path"] == "/v1/analyze"
    assert request["payload"] == {"symbol": "600519.SH", "trade_date": "2026-07-22"}
    assert AshareServiceConfig().enabled is False


def test_contract_rejects_ambiguous_symbol_and_bad_job_acknowledgement():
    with pytest.raises(AshareContractError):
        normalize_ashare_symbol("AAPL")
    with pytest.raises(AshareContractError):
        validate_ashare_job_response({})
    assert validate_ashare_job_response({"job_id": "abc-123"}) == {"job_id": "abc-123"}
