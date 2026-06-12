from __future__ import annotations

from pathlib import Path

from .model import GitSnapshot
from .process import run_capture
from .redaction import redact_text


def git_output(repo: Path, args: list[str]) -> tuple[int, str, str]:
    result = run_capture(["git", *args], repo)
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def require_git_repo(repo: Path) -> None:
    code, output, err = git_output(repo, ["rev-parse", "--show-toplevel"])
    if code != 0:
        raise SystemExit(f"Not a git repository: {repo}\n{err or output}")


def snapshot(repo: Path) -> GitSnapshot:
    require_git_repo(repo)
    _, root, _ = git_output(repo, ["rev-parse", "--show-toplevel"])
    head_code, head, _ = git_output(repo, ["rev-parse", "HEAD"])
    branch_code, branch, _ = git_output(repo, ["branch", "--show-current"])
    _, status, _ = git_output(repo, ["status", "--short"])
    _, diff_stat, _ = git_output(repo, ["diff", "--stat"])
    _, diff, _ = git_output(repo, ["diff", "--binary"])
    return GitSnapshot(
        repo=root or str(repo),
        head=head if head_code == 0 else None,
        branch=branch if branch_code == 0 and branch else None,
        status=redact_text(status),
        diff_stat=redact_text(diff_stat),
        diff=redact_text(diff),
    )
