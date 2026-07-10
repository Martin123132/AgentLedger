from __future__ import annotations

import subprocess
from pathlib import Path

from agentledger.environment import DEPENDENCY_LOCK_LIMIT, ENVIRONMENT_SCHEMA, capture_environment


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return result.stdout.strip()


def _make_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "environment-test@example.local")
    _git(repo, "config", "user.name", "AgentLedger Environment Test")
    (repo / "README.md").write_text("# Environment test\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "initial")
    return repo


def test_environment_lock_fingerprints_are_bounded_and_tracked_only(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    lock_count = DEPENDENCY_LOCK_LIMIT + 3
    for index in range(lock_count):
        folder = repo / f"package-{index:02d}"
        folder.mkdir()
        (folder / "package-lock.json").write_text(f'{{"index":{index}}}\n', encoding="utf-8")
    deleted_lock = repo / "requirements.txt"
    deleted_lock.write_text("deleted-before-capture==1\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "add many lockfiles")
    deleted_lock.unlink()
    (repo / "poetry.lock").write_text("untracked and private\n", encoding="utf-8")
    base_commit = _git(repo, "rev-parse", "HEAD")

    fingerprint = capture_environment(repo, base_commit=base_commit, agentledger_version="test-version")
    payload = fingerprint.to_dict()

    assert payload["schema_version"] == ENVIRONMENT_SCHEMA
    assert payload["agentledger_version"] == "test-version"
    assert payload["base_commit"] == base_commit
    assert payload["dependency_lock_count"] == lock_count
    assert payload["dependency_lock_limit"] == DEPENDENCY_LOCK_LIMIT
    assert payload["dependency_locks_truncated"] is True
    assert len(payload["dependency_locks"]) == DEPENDENCY_LOCK_LIMIT
    assert all(item["path"].endswith("package-lock.json") for item in payload["dependency_locks"])
    assert all(item["ecosystem"] == "javascript" for item in payload["dependency_locks"])
    assert all(len(item["sha256"]) == 64 for item in payload["dependency_locks"])
    assert all(item["path"] != "poetry.lock" for item in payload["dependency_locks"])
    assert payload["privacy"] == {
        "environment_variables_included": False,
        "executable_paths_included": False,
        "hostnames_included": False,
        "file_contents_included": False,
    }
