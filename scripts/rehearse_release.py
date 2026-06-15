from __future__ import annotations

import argparse
from datetime import date
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import ModuleType
from typing import Any
import uuid


ROOT = Path(__file__).resolve().parents[1]
PREPARE_RELEASE_SCRIPT = ROOT / "scripts" / "prepare_release.py"
RELEASE_NOTES_SCRIPT = ROOT / "scripts" / "release_notes.py"
RELEASE_CHECK_SUMMARY_SCRIPT = ROOT / "scripts" / "release_check_summary.py"


class ReleaseRehearsalError(ValueError):
    pass


def load_script(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ReleaseRehearsalError(f"Could not load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


prepare_release = load_script("agentledger_prepare_release_rehearsal", PREPARE_RELEASE_SCRIPT)
release_notes = load_script("agentledger_release_notes_rehearsal", RELEASE_NOTES_SCRIPT)
release_check_summary = load_script(
    "agentledger_release_check_summary_rehearsal",
    RELEASE_CHECK_SUMMARY_SCRIPT,
)


def run_command(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )


def run_git(repo_root: Path, args: list[str]) -> str:
    completed = run_command(["git", *args], cwd=repo_root)
    if completed.returncode != 0:
        output = completed.stdout.strip()
        raise ReleaseRehearsalError(
            f"git {' '.join(args)} failed"
            + (f": {output}" if output else f" with code {completed.returncode}")
        )
    return completed.stdout.strip()


def add_step(
    result: dict[str, Any],
    *,
    name: str,
    status: str,
    detail: str,
    data: dict[str, Any] | None = None,
) -> None:
    step: dict[str, Any] = {
        "name": name,
        "status": status,
        "detail": detail,
    }
    if data:
        step.update(data)
    result["steps"].append(step)


def default_output_dir(version: str) -> Path:
    release_version = prepare_release.changelog_version(version)
    return Path(tempfile.gettempdir()) / f"agentledger-release-rehearsal-{release_version}-{uuid.uuid4().hex[:8]}"


def collect_git_state(repo_root: Path, *, require_clean_git: bool) -> dict[str, Any]:
    try:
        branch = run_git(repo_root, ["branch", "--show-current"])
        head = run_git(repo_root, ["rev-parse", "--short", "HEAD"])
        status = run_git(repo_root, ["status", "--short", "--untracked-files=all"])
        run_git(repo_root, ["diff", "--check"])
    except ReleaseRehearsalError:
        if require_clean_git:
            raise
        return {
            "branch": None,
            "head": None,
            "working_tree_dirty": None,
            "status": None,
            "skipped": True,
        }

    if require_clean_git and status:
        raise ReleaseRehearsalError("Working tree is not clean:\n" + status)

    return {
        "branch": branch,
        "head": head,
        "working_tree_dirty": bool(status),
        "status": status,
        "skipped": False,
    }


def build_draft_notes(repo_root: Path, *, version: str, release_date: str) -> str:
    changelog_text = (repo_root / "CHANGELOG.md").read_text(encoding="utf-8-sig")
    prepared_changelog = prepare_release.prepare_changelog(
        changelog_text=changelog_text,
        package_version=version,
        release_date=release_date,
    )
    return release_notes.build_release_notes(
        version=version,
        changelog_text=prepared_changelog,
    )


def find_powershell() -> str | None:
    for candidate in ("pwsh", "powershell"):
        path = shutil.which(candidate)
        if path:
            return path
    return None


def run_release_check(repo_root: Path, output_dir: Path) -> dict[str, Any]:
    shell = find_powershell()
    if shell is None:
        raise ReleaseRehearsalError("Could not find pwsh or powershell for release-check.ps1.")

    json_path = output_dir / "release-check.json"
    summary_path = output_dir / "release-check-summary.md"
    log_path = output_dir / "release-check.log"
    command = [
        shell,
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(repo_root / "scripts" / "release-check.ps1"),
        "-RequireCleanGit",
        "-JsonOutput",
        str(json_path),
    ]
    completed = run_command(command, cwd=repo_root)
    log_path.write_text(completed.stdout, encoding="utf-8")

    if completed.returncode != 0:
        raise ReleaseRehearsalError(
            f"release-check.ps1 failed with code {completed.returncode}; see {log_path}"
        )
    if not json_path.exists():
        raise ReleaseRehearsalError("release-check.ps1 did not write its JSON summary.")

    payload = json.loads(json_path.read_text(encoding="utf-8-sig"))
    if payload.get("ok") is not True:
        raise ReleaseRehearsalError(f"release-check.ps1 summary was not OK: {json_path}")
    summary_path.write_text(
        release_check_summary.render_release_check_markdown(payload),
        encoding="utf-8",
    )
    return {
        "json": str(json_path),
        "summary": str(summary_path),
        "log": str(log_path),
        "status": payload.get("status"),
        "steps": len(payload.get("steps", [])),
    }


def write_markdown_summary(result: dict[str, Any], path: Path) -> None:
    lines = [
        "# AgentLedger Release Rehearsal",
        "",
        f"- Status: {result['status']}",
        f"- Package version: {result['package_version']}",
        f"- Release label: {result['release_version']}",
        f"- Release date: {result['release_date']}",
        f"- Repository: {result['repo']}",
    ]
    if result.get("branch") or result.get("head"):
        lines.extend(
            [
                f"- Branch: {result.get('branch') or 'unknown'}",
                f"- HEAD: {result.get('head') or 'unknown'}",
            ]
        )
    lines.extend(
        [
            "",
            "## Outputs",
            "",
            f"- Draft release notes: {result.get('draft_release_notes') or 'not written'}",
            f"- JSON summary: {result.get('summary_json') or path.with_suffix('.json')}",
        ]
    )
    if result.get("release_check_json"):
        lines.append(f"- Release-check JSON: {result['release_check_json']}")
    if result.get("release_check_summary"):
        lines.append(f"- Release-check summary: {result['release_check_summary']}")
    if result.get("release_check_log"):
        lines.append(f"- Release-check log: {result['release_check_log']}")

    lines.extend(["", "## Checklist", ""])
    for step in result["steps"]:
        marker = "[x]" if step["status"] == "passed" else "[-]" if step["status"] in {"skipped", "pending"} else "[ ]"
        lines.append(f"- {marker} {step['name']}: {step['detail']}")

    lines.extend(
        [
            "",
            "## Next",
            "",
            "- Review the draft release notes and replace validation TODOs with real links before publishing.",
            "- Use the release-check JSON and summary paths when finalizing release notes and building the post-release evidence packet.",
            "- Keep rehearsal output outside the repository or delete it before committing.",
        ]
    )
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def finalize_result(result: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    failed = [step for step in result["steps"] if step["status"] == "failed"]
    result["ok"] = not failed
    result["status"] = "rehearsal_passed" if result["ok"] else "failed"
    summary_json = output_dir / "release-rehearsal-summary.json"
    summary_md = output_dir / "release-rehearsal-summary.md"
    result["summary_json"] = str(summary_json)
    result["summary_markdown"] = str(summary_md)
    summary_json.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    write_markdown_summary(result, summary_md)
    return result


def rehearse_release(
    *,
    repo_root: Path,
    version: str,
    release_date: str,
    output_dir: Path,
    require_clean_git: bool = True,
    run_full_release_check: bool = True,
) -> dict[str, Any]:
    root = repo_root.resolve()
    out = output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)

    package_version = prepare_release.validate_package_version(version)
    normalized_date = prepare_release.validate_release_date(release_date)
    release_version = prepare_release.changelog_version(package_version)
    draft_notes = out / f"agentledger-{release_version}-release.md"

    result: dict[str, Any] = {
        "schema_version": "agentledger.release_rehearsal.v1",
        "ok": False,
        "status": "running",
        "repo": str(root),
        "package_version": package_version,
        "release_version": release_version,
        "release_date": normalized_date,
        "output_dir": str(out),
        "draft_release_notes": str(draft_notes),
        "release_check_json": None,
        "release_check_summary": None,
        "release_check_log": None,
        "branch": None,
        "head": None,
        "working_tree_dirty": None,
        "steps": [],
    }

    try:
        git_state = collect_git_state(root, require_clean_git=require_clean_git)
        result.update(
            branch=git_state["branch"],
            head=git_state["head"],
            working_tree_dirty=git_state["working_tree_dirty"],
        )
        if git_state["skipped"]:
            add_step(
                result,
                name="Git hygiene",
                status="skipped",
                detail="Skipped because --allow-dirty was used outside a git checkout.",
            )
        else:
            add_step(
                result,
                name="Git hygiene",
                status="passed",
                detail=(
                    "Working tree is clean."
                    if not git_state["working_tree_dirty"]
                    else "Working tree has changes."
                ),
            )
    except Exception as error:
        add_step(result, name="Git hygiene", status="failed", detail=str(error))
        return finalize_result(result, out)

    try:
        prep = prepare_release.prepare_release(
            repo_root=root,
            version=package_version,
            release_date=normalized_date,
            release_notes_output=draft_notes,
            dry_run=True,
        )
        add_step(
            result,
            name="Release prep dry run",
            status="passed",
            detail="No source files written.",
            data={"changed_files": list(prep.changed_files)},
        )
    except Exception as error:
        add_step(result, name="Release prep dry run", status="failed", detail=str(error))
        return finalize_result(result, out)

    try:
        notes_text = build_draft_notes(root, version=package_version, release_date=normalized_date)
        draft_notes.write_text(notes_text, encoding="utf-8")
        add_step(
            result,
            name="Draft release notes",
            status="passed",
            detail=f"Wrote draft notes outside the repo: {draft_notes}",
        )
    except Exception as error:
        add_step(result, name="Draft release notes", status="failed", detail=str(error))
        return finalize_result(result, out)

    try:
        release_notes.validate_publish_ready(version=package_version, notes_text=notes_text)
    except Exception as error:
        detail = str(error)
        status = "pending" if "TODO" in detail else "failed"
        add_step(
            result,
            name="Publish-ready notes check",
            status=status,
            detail=(
                "Draft notes still need real validation links before publishing."
                if status == "pending"
                else detail
            ),
        )
        if status == "failed":
            return finalize_result(result, out)
    else:
        add_step(
            result,
            name="Publish-ready notes check",
            status="passed",
            detail="Draft notes are already publish-ready.",
        )

    if run_full_release_check:
        try:
            release_check = run_release_check(root, out)
            result["release_check_json"] = release_check["json"]
            result["release_check_summary"] = release_check["summary"]
            result["release_check_log"] = release_check["log"]
            add_step(
                result,
                name="Release readiness check",
                status="passed",
                detail=f"release-check.ps1 passed with {release_check['steps']} recorded steps.",
            )
        except Exception as error:
            add_step(result, name="Release readiness check", status="failed", detail=str(error))
            return finalize_result(result, out)
    else:
        add_step(
            result,
            name="Release readiness check",
            status="skipped",
            detail="Skipped by --skip-release-check.",
        )

    return finalize_result(result, out)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Dry-run the AgentLedger alpha release flow and write a local checklist summary."
    )
    parser.add_argument(
        "--version",
        required=True,
        help="PEP 440 package version to rehearse, for example 0.1.8a0.",
    )
    parser.add_argument(
        "--date",
        default=date.today().isoformat(),
        help="Release date in YYYY-MM-DD format. Defaults to today.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=ROOT,
        help="Repository root. Defaults to this script's parent repository.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Directory for rehearsal summaries and draft notes. Defaults to a temp directory.",
    )
    parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="Allow a dirty working tree during rehearsal. Do not use this before tagging.",
    )
    parser.add_argument(
        "--skip-release-check",
        action="store_true",
        help="Skip scripts/release-check.ps1. Useful only for quick local script checks.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        output_dir = args.output_dir or default_output_dir(args.version)
        result = rehearse_release(
            repo_root=args.repo_root,
            version=args.version,
            release_date=args.date,
            output_dir=output_dir,
            require_clean_git=not args.allow_dirty,
            run_full_release_check=not args.skip_release_check,
        )
    except (OSError, ReleaseRehearsalError) as error:
        print(f"rehearse_release.py: {error}", file=sys.stderr)
        return 2

    print(f"Release rehearsal: {result['package_version']} -> {result['release_version']}")
    print(f"Status: {result['status']}")
    print(f"Summary: {result['summary_markdown']}")
    print(f"JSON: {result['summary_json']}")
    print(f"Draft notes: {result['draft_release_notes']}")
    if result.get("release_check_json"):
        print(f"Release-check JSON: {result['release_check_json']}")
    if result.get("release_check_summary"):
        print(f"Release-check summary: {result['release_check_summary']}")

    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
