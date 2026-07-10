from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class CommandResult:
    command: list[str]
    cwd: str
    started_at: str
    ended_at: str
    exit_code: int
    stdout_tail: str = ""
    stderr_tail: str = ""
    stdout_path: str | None = None
    stderr_path: str | None = None
    test_detected: bool = False
    test_framework: str | None = None
    duration_seconds: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "cwd": self.cwd,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "exit_code": self.exit_code,
            "duration_seconds": self.duration_seconds,
            "stdout_tail": self.stdout_tail,
            "stderr_tail": self.stderr_tail,
            "stdout_path": self.stdout_path,
            "stderr_path": self.stderr_path,
            "test_detected": self.test_detected,
            "test_framework": self.test_framework,
        }


@dataclass
class DependencyLockFingerprint:
    path: str
    ecosystem: str
    size: int
    sha256: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "ecosystem": self.ecosystem,
            "size": self.size,
            "sha256": self.sha256,
        }


@dataclass
class EnvironmentFingerprint:
    schema_version: str
    agentledger_version: str
    os: dict[str, str]
    python: dict[str, str]
    git_version: str
    base_commit: str | None
    dependency_locks: list[DependencyLockFingerprint]
    dependency_lock_count: int
    dependency_lock_limit: int
    dependency_locks_truncated: bool
    privacy: dict[str, bool]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "agentledger_version": self.agentledger_version,
            "os": self.os,
            "python": self.python,
            "git_version": self.git_version,
            "base_commit": self.base_commit,
            "dependency_locks": [item.to_dict() for item in self.dependency_locks],
            "dependency_lock_count": self.dependency_lock_count,
            "dependency_lock_limit": self.dependency_lock_limit,
            "dependency_locks_truncated": self.dependency_locks_truncated,
            "privacy": self.privacy,
        }


@dataclass
class ReportIntegrity:
    schema_version: str
    algorithm: str
    canonicalization: str
    report_sha256: str
    previous_run_id: str | None
    previous_report_sha256: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "algorithm": self.algorithm,
            "canonicalization": self.canonicalization,
            "report_sha256": self.report_sha256,
            "previous_run_id": self.previous_run_id,
            "previous_report_sha256": self.previous_report_sha256,
        }


@dataclass
class GitFileState:
    path: str
    status: str
    tracked: bool
    size: int | None = None
    sha256: str | None = None
    original_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "status": self.status,
            "tracked": self.tracked,
            "size": self.size,
            "sha256": self.sha256,
            "original_path": self.original_path,
        }


@dataclass
class GitSnapshot:
    repo: str
    head: str | None
    branch: str | None
    status: str
    diff_stat: str
    diff: str
    files: list[GitFileState] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "repo": self.repo,
            "head": self.head,
            "branch": self.branch,
            "status": self.status,
            "diff_stat": self.diff_stat,
            "diff": self.diff,
            "files": [file.to_dict() for file in self.files],
        }


@dataclass
class ChangeSet:
    added: list[str] = field(default_factory=list)
    modified: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    renamed: list[dict[str, str]] = field(default_factory=list)
    restored: list[str] = field(default_factory=list)

    @property
    def changed_file_count(self) -> int:
        paths = set(self.added + self.modified + self.deleted + self.restored)
        paths.update(item["to"] for item in self.renamed)
        return len(paths)

    def to_dict(self) -> dict[str, Any]:
        return {
            "added": self.added,
            "modified": self.modified,
            "deleted": self.deleted,
            "renamed": self.renamed,
            "restored": self.restored,
            "changed_file_count": self.changed_file_count,
        }


@dataclass
class ChangeAttribution:
    available: bool
    basis: list[str]
    preexisting_dirty: list[str]
    changed_during_run: ChangeSet
    committed_during_run: ChangeSet
    working_tree_during_run: ChangeSet
    unchanged_preexisting: list[str]
    head_changed: bool
    limitations: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "available": self.available,
            "basis": self.basis,
            "preexisting_dirty": self.preexisting_dirty,
            "changed_during_run": self.changed_during_run.to_dict(),
            "committed_during_run": self.committed_during_run.to_dict(),
            "working_tree_during_run": self.working_tree_during_run.to_dict(),
            "unchanged_preexisting": self.unchanged_preexisting,
            "head_changed": self.head_changed,
            "limitations": self.limitations,
        }


@dataclass
class ToolArtifact:
    name: str
    ok: bool
    command: list[str] = field(default_factory=list)
    output_path: str | None = None
    summary: str = ""
    exit_code: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "ok": self.ok,
            "command": self.command,
            "output_path": self.output_path,
            "summary": self.summary,
            "exit_code": self.exit_code,
        }


@dataclass
class LedgerReport:
    schema_version: str
    run_id: str
    started_at: str
    ended_at: str
    target_repo: str
    command: CommandResult | None
    before: GitSnapshot
    after: GitSnapshot
    privacy_mode: str = "standard"
    artifacts: list[ToolArtifact] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    change_attribution: ChangeAttribution | None = None
    environment: EnvironmentFingerprint | None = None
    integrity: ReportIntegrity | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "target_repo": self.target_repo,
            "command": self.command.to_dict() if self.command else None,
            "before": self.before.to_dict(),
            "after": self.after.to_dict(),
            "privacy_mode": self.privacy_mode,
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "warnings": self.warnings,
            "change_attribution": self.change_attribution.to_dict() if self.change_attribution else None,
            "environment": self.environment.to_dict() if self.environment else None,
            "integrity": self.integrity.to_dict() if self.integrity else None,
        }
