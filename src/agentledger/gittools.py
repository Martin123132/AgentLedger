from __future__ import annotations

import hashlib
import os
from pathlib import Path

from .model import ChangeAttribution, ChangeSet, GitFileState, GitSnapshot
from .process import run_capture
from .redaction import redact_text


ATTRIBUTION_LIMITATIONS = [
    "Attribution compares Git HEAD and working-tree state at the command boundaries.",
    "Changes made and fully reverted during the command are not observable.",
    "A file already dirty before the command remains identified as pre-existing even if the command later commits it.",
]


def git_output(repo: Path, args: list[str]) -> tuple[int, str, str]:
    result = run_capture(["git", *args], repo)
    return result.returncode, result.stdout.strip(), result.stderr.strip()


def require_git_repo(repo: Path) -> None:
    code, output, err = git_output(repo, ["rev-parse", "--show-toplevel"])
    if code != 0:
        raise SystemExit(f"Not a git repository: {repo}\n{err or output}")


def snapshot(repo: Path, *, excluded_paths: list[Path] | None = None) -> GitSnapshot:
    require_git_repo(repo)
    _, root, _ = git_output(repo, ["rev-parse", "--show-toplevel"])
    repo_root = Path(root or repo).resolve()
    exclusions = _relative_exclusions(repo_root, excluded_paths or [])
    head_code, head, _ = git_output(repo, ["rev-parse", "HEAD"])
    branch_code, branch, _ = git_output(repo, ["branch", "--show-current"])
    diff_args = _diff_pathspec(exclusions)
    _, diff_stat, _ = git_output(repo, ["diff", "--stat", *diff_args])
    _, diff, _ = git_output(repo, ["diff", "--binary", *diff_args])
    files = _working_tree_files(repo_root, exclusions)
    status = _format_status(files)
    return GitSnapshot(
        repo=root or str(repo),
        head=head if head_code == 0 else None,
        branch=branch if branch_code == 0 and branch else None,
        status=redact_text(status),
        diff_stat=redact_text(diff_stat),
        diff=redact_text(diff),
        files=files,
    )


def build_change_attribution(repo: Path, before: GitSnapshot, after: GitSnapshot, *, available: bool) -> ChangeAttribution:
    preexisting = sorted(file.path for file in before.files)
    if not available:
        return ChangeAttribution(
            available=False,
            basis=[],
            preexisting_dirty=preexisting,
            changed_during_run=ChangeSet(),
            committed_during_run=ChangeSet(),
            working_tree_during_run=ChangeSet(),
            unchanged_preexisting=preexisting,
            head_changed=before.head != after.head,
            limitations=ATTRIBUTION_LIMITATIONS,
        )

    working_tree, unchanged_preexisting = _working_tree_changes(before.files, after.files)
    committed = _committed_changes(repo, before.head, after.head)
    combined = _merge_change_sets(committed, working_tree)
    basis = ["working-tree-fingerprint"]
    if before.head != after.head:
        basis.insert(0, "git-head-range")
    return ChangeAttribution(
        available=True,
        basis=basis,
        preexisting_dirty=preexisting,
        changed_during_run=combined,
        committed_during_run=committed,
        working_tree_during_run=working_tree,
        unchanged_preexisting=unchanged_preexisting,
        head_changed=before.head != after.head,
        limitations=ATTRIBUTION_LIMITATIONS,
    )


def _working_tree_files(repo: Path, exclusions: list[str]) -> list[GitFileState]:
    result = run_capture(
        ["git", "-c", "core.quotepath=false", "status", "--porcelain=v2", "-z", "--untracked-files=all"],
        repo,
    )
    if result.returncode != 0:
        return []

    records = result.stdout.split("\0")
    files: list[GitFileState] = []
    index = 0
    while index < len(records):
        record = records[index]
        index += 1
        if not record:
            continue
        parsed = _parse_status_record(record)
        if parsed is None:
            continue
        status, path, tracked, expects_original = parsed
        original_path = None
        if expects_original and index < len(records):
            original_path = records[index]
            index += 1
        if _path_excluded(path, exclusions) or (original_path and _path_excluded(original_path, exclusions)):
            continue
        size, sha256 = _file_fingerprint(repo, path)
        files.append(
            GitFileState(
                path=redact_text(path),
                status=status,
                tracked=tracked,
                size=size,
                sha256=sha256,
                original_path=redact_text(original_path) if original_path else None,
            )
        )
    return sorted(files, key=lambda item: item.path)


def _relative_exclusions(repo: Path, paths: list[Path]) -> list[str]:
    output = []
    for path in paths:
        try:
            relative = path.resolve().relative_to(repo).as_posix().rstrip("/")
        except ValueError:
            continue
        if relative and relative != ".":
            output.append(relative)
    return sorted(set(output))


def _path_excluded(path: str, exclusions: list[str]) -> bool:
    normalized = path.replace("\\", "/").rstrip("/")
    return any(normalized == item or normalized.startswith(f"{item}/") for item in exclusions)


def _diff_pathspec(exclusions: list[str]) -> list[str]:
    if not exclusions:
        return []
    pathspec = ["--", "."]
    for item in exclusions:
        pathspec.extend([f":(exclude,top){item}", f":(exclude,top){item}/**"])
    return pathspec


def _format_status(files: list[GitFileState]) -> str:
    lines = []
    for file in files:
        path = f"{file.original_path} -> {file.path}" if file.original_path else file.path
        lines.append(f"{file.status.replace('.', ' ')} {path}")
    return "\n".join(lines)


def _parse_status_record(record: str) -> tuple[str, str, bool, bool] | None:
    if record.startswith("1 "):
        parts = record.split(" ", 8)
        return (parts[1], parts[8], True, False) if len(parts) == 9 else None
    if record.startswith("2 "):
        parts = record.split(" ", 9)
        return (parts[1], parts[9], True, True) if len(parts) == 10 else None
    if record.startswith("u "):
        parts = record.split(" ", 10)
        return (parts[1], parts[10], True, False) if len(parts) == 11 else None
    if record.startswith("? "):
        return "??", record[2:], False, False
    return None


def _file_fingerprint(repo: Path, path: str) -> tuple[int | None, str | None]:
    candidate = repo / Path(path)
    try:
        if candidate.is_symlink():
            target = os.readlink(candidate)
            content = os.fsencode(target)
            return len(content), hashlib.sha256(content).hexdigest()
        if not candidate.is_file():
            return None, None
        size = candidate.stat().st_size
        digest = hashlib.sha256()
        with candidate.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return size, digest.hexdigest()
    except OSError:
        return None, None


def _same_file_state(before: GitFileState, after: GitFileState) -> bool:
    return (
        before.status,
        before.tracked,
        before.size,
        before.sha256,
        before.original_path,
    ) == (
        after.status,
        after.tracked,
        after.size,
        after.sha256,
        after.original_path,
    )


def _working_tree_changes(before_files: list[GitFileState], after_files: list[GitFileState]) -> tuple[ChangeSet, list[str]]:
    before = {file.path: file for file in before_files}
    after = {file.path: file for file in after_files}
    changes = ChangeSet()
    unchanged: list[str] = []
    consumed_before: set[str] = set()
    consumed_after: set[str] = set()

    for path, current in sorted(after.items()):
        previous = before.get(path)
        if not current.original_path or (previous is not None and _same_file_state(previous, current)):
            continue
        changes.renamed.append({"from": current.original_path, "to": path})
        consumed_after.add(path)
        consumed_before.add(current.original_path)

    for path in sorted(set(before) | set(after)):
        if path in consumed_before or path in consumed_after:
            continue
        previous = before.get(path)
        current = after.get(path)
        if previous is not None and current is not None:
            if _same_file_state(previous, current):
                unchanged.append(path)
            elif _is_deleted(current):
                changes.deleted.append(path)
            else:
                changes.modified.append(path)
        elif current is not None:
            if _is_deleted(current):
                changes.deleted.append(path)
            elif not current.tracked or "A" in current.status:
                changes.added.append(path)
            else:
                changes.modified.append(path)
        elif previous is not None:
            if previous.tracked:
                changes.restored.append(path)
            else:
                changes.deleted.append(path)
    return _sorted_change_set(changes), sorted(unchanged)


def _is_deleted(file: GitFileState) -> bool:
    return "D" in file.status and file.sha256 is None


def _committed_changes(repo: Path, before_head: str | None, after_head: str | None) -> ChangeSet:
    if not before_head or not after_head or before_head == after_head:
        return ChangeSet()
    result = run_capture(
        ["git", "diff", "--name-status", "-z", "--find-renames", before_head, after_head],
        repo,
    )
    if result.returncode != 0:
        return ChangeSet()
    fields = result.stdout.split("\0")
    changes = ChangeSet()
    index = 0
    while index < len(fields):
        status = fields[index]
        index += 1
        if not status or index >= len(fields):
            continue
        code = status[0]
        path = redact_text(fields[index])
        index += 1
        if code in {"R", "C"}:
            if index >= len(fields):
                break
            target = redact_text(fields[index])
            index += 1
            if code == "R":
                changes.renamed.append({"from": path, "to": target})
            else:
                changes.added.append(target)
        elif code == "A":
            changes.added.append(path)
        elif code == "D":
            changes.deleted.append(path)
        else:
            changes.modified.append(path)
    return _sorted_change_set(changes)


def _merge_change_sets(first: ChangeSet, second: ChangeSet) -> ChangeSet:
    return _sorted_change_set(
        ChangeSet(
            added=list(dict.fromkeys(first.added + second.added)),
            modified=list(dict.fromkeys(first.modified + second.modified)),
            deleted=list(dict.fromkeys(first.deleted + second.deleted)),
            renamed=_unique_renames(first.renamed + second.renamed),
            restored=list(dict.fromkeys(first.restored + second.restored)),
        )
    )


def _unique_renames(items: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str]] = set()
    output = []
    for item in items:
        key = (item["from"], item["to"])
        if key not in seen:
            seen.add(key)
            output.append(item)
    return output


def _sorted_change_set(changes: ChangeSet) -> ChangeSet:
    changes.added.sort()
    changes.modified.sort()
    changes.deleted.sort()
    changes.renamed.sort(key=lambda item: (item["from"], item["to"]))
    changes.restored.sort()
    return changes
