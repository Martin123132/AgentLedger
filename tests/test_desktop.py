from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from agentledger.desktop_core import capture_repository, load_dashboard, split_command_line
from scripts.write_desktop_icon import write_icon
from scripts.write_desktop_manifest import SCHEMA_VERSION, build_manifest


@pytest.mark.skipif(sys.platform != "win32", reason="desktop UI is Windows-only")
def test_desktop_main_supports_packaged_smoke_test(monkeypatch) -> None:
    from agentledger import desktop

    events: list[str] = []

    class FakeRoot:
        def withdraw(self) -> None:
            events.append("withdraw")

        def update_idletasks(self) -> None:
            events.append("update")

        def destroy(self) -> None:
            events.append("destroy")

    monkeypatch.setattr(desktop, "Tk", FakeRoot)
    monkeypatch.setattr(desktop, "AgentLedgerDesktop", lambda root: events.append("app"))

    assert desktop.main(["--smoke-test"]) == 0
    assert events == ["app", "withdraw", "update", "destroy"]
    assert desktop.public_version("0.1.33a0") == "v0.1.33-alpha"
    assert desktop.format_run_id("2026-07-19T192521Z0000-abc12345") == "2026-07-19 19:25 UTC"


def test_desktop_icon_is_valid_embedded_png(tmp_path: Path) -> None:
    icon = tmp_path / "agentledger.ico"

    write_icon(icon)
    data = icon.read_bytes()

    assert data[:6] == b"\x00\x00\x01\x00\x01\x00"
    assert data[22:30] == b"\x89PNG\r\n\x1a\n"
    assert len(data) > 1_000


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def test_split_command_line_preserves_quoted_arguments() -> None:
    assert split_command_line('python -c "print(123)"') == ["python", "-c", "print(123)"]


def test_dashboard_handles_repo_without_evidence(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()

    dashboard = load_dashboard(repo)

    assert dashboard["status"]["status"] == "unknown"
    assert dashboard["history"] == []
    assert dashboard["status"]["errors"]


def test_desktop_capture_uses_existing_cli_engine(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "desktop@example.local")
    _git(repo, "config", "user.name", "AgentLedger Desktop")
    (repo / "README.md").write_text("desktop\n", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "init")
    command = subprocess.list2cmdline([sys.executable, "-c", "print('desktop capture')"])

    result = capture_repository(repo, command, zip_bundle=False)
    dashboard = load_dashboard(repo)

    assert result.exit_code == 0
    assert dashboard["status"]["latest_run"]
    assert len(dashboard["history"]) == 1


def test_desktop_manifest_hashes_artifacts_without_absolute_paths(tmp_path: Path) -> None:
    executable = tmp_path / "AgentLedger.exe"
    installer = tmp_path / "AgentLedger-setup.exe"
    portable = tmp_path / "AgentLedger-portable.zip"
    executable.write_bytes(b"desktop exe")
    installer.write_bytes(b"installer")
    portable.write_bytes(b"portable")

    payload = build_manifest(
        version="0.1.33a0",
        executable=executable,
        installer=installer,
        portable=portable,
        source_commit="abc123",
    )
    encoded = json.dumps(payload)

    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["release_label"] == "v0.1.33-alpha"
    assert payload["install_scope"] == "per_user"
    assert payload["artifacts"]["executable"]["sha256"] == hashlib.sha256(b"desktop exe").hexdigest()
    assert str(tmp_path) not in encoded


def test_desktop_build_contract_is_checked() -> None:
    root = Path(__file__).resolve().parents[1]
    workflow = (root / ".github" / "workflows" / "desktop.yml").read_text(encoding="utf-8")
    build = (root / "scripts" / "build-desktop.ps1").read_text(encoding="utf-8")
    installer = (root / "packaging" / "windows" / "AgentLedger.iss").read_text(encoding="utf-8")

    assert "release:\n    types: [published]" in workflow
    assert "gh release upload" in workflow
    assert "AgentLedger-$releaseVersion-windows-x64-setup.exe" in build
    assert "AgentLedger-$releaseVersion-windows-x64-portable.zip" in build
    assert "DefaultDirName={localappdata}\\Programs\\AgentLedger" in installer
    assert "UninstallDisplayIcon={app}\\AgentLedger.exe" in installer
