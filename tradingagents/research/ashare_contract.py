"""Versioned, non-executing contract for a separate TradingAgents-AShare service.

No HTTP request is made here. The contract makes the small data boundary
auditable before an operator independently configures and starts the separately
licensed service.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
import re
from typing import Any, Mapping


ASHARE_CONTRACT_VERSION = "1.0"
_CN_SYMBOL = re.compile(r"^(?P<code>\d{6})(?:\.(?P<suffix>SS|SZ|BJ|SH))?$")


class AshareContractError(ValueError):
    """Raised when an external-service request would be ambiguous or unsafe."""


@dataclass(frozen=True)
class AshareServiceConfig:
    """Operator-owned configuration; disabled until explicitly enabled elsewhere."""

    enabled: bool = False
    base_url: str = "http://127.0.0.1:8010"
    timeout_seconds: int = 60

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalize_ashare_symbol(symbol: str) -> str:
    """Map the local suffix convention to a documented A-share API symbol."""
    match = _CN_SYMBOL.match(symbol.upper().strip())
    if not match:
        raise AshareContractError(
            "TradingAgents-AShare requests require a six-digit China/Beijing symbol."
        )
    code, suffix = match.group("code"), match.group("suffix")
    if suffix == "BJ" or code.startswith(("4", "8", "9")):
        return f"{code}.BJ"
    if suffix in {"SS", "SH"} or code.startswith("6"):
        return f"{code}.SH"
    return f"{code}.SZ"


def build_ashare_analysis_request(symbol: str, trade_date: str | date) -> dict[str, Any]:
    """Build the documented ``POST /v1/analyze`` payload without sending it.

    Research context stays local: only the normalized target and analysis date
    cross this licence/service boundary. The returned envelope includes the
    endpoint and schema version so an operator can implement transport later.
    """
    normalized_date = date.fromisoformat(str(trade_date)).isoformat()
    return {
        "contract_version": ASHARE_CONTRACT_VERSION,
        "method": "POST",
        "path": "/v1/analyze",
        "payload": {
            "symbol": normalize_ashare_symbol(symbol),
            "trade_date": normalized_date,
        },
        "expected_response": {
            "job_id": "string",
            "status_path": "/v1/jobs/{job_id}",
            "result_path": "/v1/jobs/{job_id}/result",
        },
        "boundary_note": "Local research context is not transmitted to the separate service.",
    }


def validate_ashare_job_response(payload: Mapping[str, Any]) -> dict[str, str]:
    """Validate the minimal asynchronous acknowledgement before polling it."""
    job_id = payload.get("job_id")
    if not isinstance(job_id, str) or not job_id.strip():
        raise AshareContractError("TradingAgents-AShare response is missing a non-empty job_id.")
    return {"job_id": job_id.strip()}
