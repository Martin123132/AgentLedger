from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"


def test_ci_workflow_avoids_duplicate_feature_branch_runs() -> None:
    text = CI_WORKFLOW.read_text(encoding="utf-8")

    assert "on:\n  push:\n    branches: [master]\n    tags: [\"v*\"]\n  pull_request:" in text
    assert "concurrency:" in text
    assert "group: ${{ github.workflow }}-${{ github.ref }}" in text
    assert "cancel-in-progress: true" in text
