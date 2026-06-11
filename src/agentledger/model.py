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

    def to_dict(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "cwd": self.cwd,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "exit_code": self.exit_code,
            "stdout_tail": self.stdout_tail,
            "stderr_tail": self.stderr_tail,
        }


@dataclass
class GitSnapshot:
    repo: str
    head: str | None
    branch: str | None
    status: str
    diff_stat: str
    diff: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "repo": self.repo,
            "head": self.head,
            "branch": self.branch,
            "status": self.status,
            "diff_stat": self.diff_stat,
            "diff": self.diff,
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
    artifacts: list[ToolArtifact] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

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
            "artifacts": [artifact.to_dict() for artifact in self.artifacts],
            "warnings": self.warnings,
        }
