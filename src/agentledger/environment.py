from __future__ import annotations

import hashlib
import os
import platform
from pathlib import Path, PurePosixPath

from .model import DependencyLockFingerprint, EnvironmentFingerprint
from .process import run_capture
from .redaction import redact_text


ENVIRONMENT_SCHEMA = "agentledger.environment.v1"
DEPENDENCY_LOCK_LIMIT = 50

LOCKFILE_ECOSYSTEMS = {
    "bun.lock": "javascript",
    "bun.lockb": "javascript",
    "cargo.lock": "rust",
    "composer.lock": "php",
    "flake.lock": "nix",
    "gemfile.lock": "ruby",
    "go.sum": "go",
    "gradle.lockfile": "java",
    "npm-shrinkwrap.json": "javascript",
    "package-lock.json": "javascript",
    "package.resolved": "swift",
    "packages.lock.json": "dotnet",
    "pipfile.lock": "python",
    "pnpm-lock.yaml": "javascript",
    "poetry.lock": "python",
    "pubspec.lock": "dart",
    "uv.lock": "python",
    "yarn.lock": "javascript",
}


def capture_environment(repo: Path, *, base_commit: str | None, agentledger_version: str) -> EnvironmentFingerprint:
    candidates = _tracked_lockfiles(repo)
    fingerprints = []
    for path, ecosystem in candidates[:DEPENDENCY_LOCK_LIMIT]:
        fingerprint = _fingerprint_lockfile(repo, path, ecosystem)
        if fingerprint is not None:
            fingerprints.append(fingerprint)

    return EnvironmentFingerprint(
        schema_version=ENVIRONMENT_SCHEMA,
        agentledger_version=agentledger_version,
        os={
            "system": platform.system() or "unknown",
            "release": platform.release() or "unknown",
            "machine": platform.machine() or "unknown",
        },
        python={
            "implementation": platform.python_implementation() or "unknown",
            "version": platform.python_version() or "unknown",
        },
        git_version=_git_version(repo),
        base_commit=base_commit,
        dependency_locks=fingerprints,
        dependency_lock_count=len(candidates),
        dependency_lock_limit=DEPENDENCY_LOCK_LIMIT,
        dependency_locks_truncated=len(candidates) > DEPENDENCY_LOCK_LIMIT,
        privacy={
            "environment_variables_included": False,
            "executable_paths_included": False,
            "hostnames_included": False,
            "file_contents_included": False,
        },
    )


def _tracked_lockfiles(repo: Path) -> list[tuple[str, str]]:
    result = run_capture(["git", "-c", "core.quotepath=false", "ls-files", "-z", "--cached"], repo)
    if result.returncode != 0:
        return []
    matches = []
    for path in result.stdout.split("\0"):
        if not path:
            continue
        ecosystem = _lockfile_ecosystem(path)
        if ecosystem is not None and _tracked_path_exists(repo, path):
            matches.append((path, ecosystem))
    return sorted(matches, key=lambda item: item[0])


def _lockfile_ecosystem(path: str) -> str | None:
    name = PurePosixPath(path).name.lower()
    if name.startswith("requirements") and name.endswith(".txt"):
        return "python"
    return LOCKFILE_ECOSYSTEMS.get(name)


def _tracked_path_exists(repo: Path, path: str) -> bool:
    pure_path = PurePosixPath(path)
    if pure_path.is_absolute() or ".." in pure_path.parts:
        return False
    candidate = repo.joinpath(*pure_path.parts)
    try:
        return candidate.is_file() or candidate.is_symlink()
    except OSError:
        return False


def _fingerprint_lockfile(repo: Path, path: str, ecosystem: str) -> DependencyLockFingerprint | None:
    pure_path = PurePosixPath(path)
    if pure_path.is_absolute() or ".." in pure_path.parts:
        return None
    candidate = repo.joinpath(*pure_path.parts)
    try:
        if candidate.is_symlink():
            content = os.fsencode(os.readlink(candidate))
            size = len(content)
            digest = hashlib.sha256(content).hexdigest()
        elif candidate.is_file():
            size = candidate.stat().st_size
            hasher = hashlib.sha256()
            with candidate.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                    hasher.update(chunk)
            digest = hasher.hexdigest()
        else:
            return None
    except OSError:
        return None
    return DependencyLockFingerprint(
        path=redact_text(path),
        ecosystem=ecosystem,
        size=size,
        sha256=digest,
    )


def _git_version(repo: Path) -> str:
    result = run_capture(["git", "--version"], repo)
    if result.returncode != 0:
        return "unavailable"
    return redact_text(result.stdout.strip() or "unavailable")
