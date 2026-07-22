from __future__ import annotations

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_github_research_workflow_is_manual_only_and_read_only():
    workflow = (PROJECT_ROOT / ".github/workflows/universe-research.yml").read_text(encoding="utf-8")
    assert "workflow_dispatch:" in workflow
    assert "schedule:" not in workflow
    assert "contents: read" in workflow
    assert "actions/upload-artifact@v4" in workflow
    assert "broker" not in workflow.lower()


def test_n8n_template_is_disabled_and_has_no_credentials_or_delivery_nodes():
    payload = json.loads(
        (PROJECT_ROOT / "automation/n8n/tradingagents-research-review.disabled.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["active"] is False
    assert payload["connections"]
    serialized = json.dumps(payload).lower()
    assert "credential" not in serialized
    assert "webhook" not in serialized
    assert "telegram" not in serialized
    assert "email" not in serialized
