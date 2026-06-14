from __future__ import annotations

import configparser
from email.parser import Parser
from pathlib import Path
import subprocess
import sys
from zipfile import ZipFile

import pytest

from agentledger import __version__


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def built_wheel(tmp_path_factory: pytest.TempPathFactory) -> Path:
    wheel_dir = tmp_path_factory.mktemp("wheelhouse")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--no-deps",
            "--no-build-isolation",
            "--wheel-dir",
            str(wheel_dir),
            str(ROOT),
        ],
        cwd=ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout
    wheels = sorted(wheel_dir.glob("agentledger-*.whl"))
    assert len(wheels) == 1
    return wheels[0]


@pytest.fixture(scope="session")
def wheel_members(built_wheel: Path) -> dict[str, bytes]:
    with ZipFile(built_wheel) as archive:
        return {
            name: archive.read(name)
            for name in archive.namelist()
            if not name.endswith("/")
        }


def _dist_info_member(wheel_members: dict[str, bytes], filename: str) -> str:
    matches = [name for name in wheel_members if name.endswith(f".dist-info/{filename}")]
    assert len(matches) == 1
    return matches[0]


def test_wheel_metadata_matches_package_identity(wheel_members: dict[str, bytes]) -> None:
    metadata_text = wheel_members[_dist_info_member(wheel_members, "METADATA")].decode("utf-8")
    metadata = Parser().parsestr(metadata_text)

    assert metadata["Name"] == "agentledger"
    assert metadata["Version"] == __version__
    assert metadata["Summary"] == "Local-first black box recorder for AI coding agents."
    assert metadata["Requires-Python"] == ">=3.10"
    assert metadata["License"] == "PolyForm Noncommercial License 1.0.0"
    assert metadata["Author"] == "Martin Ollett"
    assert "Local-first black box recorder for AI coding agents." in metadata.get_payload()


def test_wheel_exposes_console_entry_point(wheel_members: dict[str, bytes]) -> None:
    entry_points = configparser.ConfigParser()
    entry_points.read_string(wheel_members[_dist_info_member(wheel_members, "entry_points.txt")].decode("utf-8"))

    assert entry_points["console_scripts"]["agentledger"] == "agentledger.cli:main"


def test_wheel_includes_agentledger_package_modules(wheel_members: dict[str, bytes]) -> None:
    source_modules = {
        path.relative_to(ROOT / "src").as_posix()
        for path in (ROOT / "src" / "agentledger").glob("*.py")
    }
    packaged_modules = {
        name
        for name in wheel_members
        if name.startswith("agentledger/") and name.endswith(".py")
    }

    assert source_modules <= packaged_modules
    assert "agentledger/cli.py" in packaged_modules
    assert "agentledger/contracts.py" in packaged_modules


def test_wheel_is_pure_python_and_has_record(wheel_members: dict[str, bytes]) -> None:
    wheel_text = wheel_members[_dist_info_member(wheel_members, "WHEEL")].decode("utf-8")

    assert "Root-Is-Purelib: true" in wheel_text
    assert "Tag: py3-none-any" in wheel_text
    assert _dist_info_member(wheel_members, "RECORD") in wheel_members
