from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path


class ConfigError(ValueError):
    """Raised when an AgentLedger config file cannot be used."""


@dataclass(frozen=True)
class AgentLedgerConfig:
    path: Path | None = None
    privacy_mode: str | None = None
    out: str | None = None
    repomori: bool | None = None
    jester: bool | None = None
    tokometer: bool | None = None
    zip: bool | None = None
    check_require_tests: bool | None = None
    check_dirty: str | None = None
    check_max_changed_files: int | None = None
    check_allow_warnings: bool | None = None


SUPPORTED_KEYS = {
    "privacy_mode": "string",
    "out": "string",
    "repomori": "bool",
    "jester": "bool",
    "tokometer": "bool",
    "zip": "bool",
    "check_require_tests": "bool",
    "check_dirty": "string",
    "check_max_changed_files": "int",
    "check_allow_warnings": "bool",
}


STARTER_CONFIG_TEXT = """# AgentLedger local policy.
# Evidence output stays local and is ignored by git when .agentledger/ is in .gitignore.
privacy_mode = "summary"
out = ".agentledger"
repomori = false
jester = false
tokometer = false
zip = true

# Review policy for agentledger check.
check_require_tests = true
check_dirty = "warn"
check_max_changed_files = 25
check_allow_warnings = true
"""


def load_config(repo: Path, config_path: str | None = None) -> AgentLedgerConfig:
    path = Path(config_path).expanduser() if config_path else repo / ".agentledger.toml"
    if not path.is_absolute():
        path = (repo / path) if config_path else path
    path = path.resolve()

    if not path.exists():
        if config_path:
            raise ConfigError(f"Config file not found: {path}")
        return AgentLedgerConfig()
    if not path.is_file():
        raise ConfigError(f"Config path is not a file: {path}")

    values = _parse_config(path)
    return AgentLedgerConfig(path=path, **values)


def _parse_config(path: Path) -> dict[str, object]:
    values: dict[str, object] = {}
    for lineno, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = _strip_inline_comment(raw_line).strip()
        if not line:
            continue
        if line.startswith("["):
            raise ConfigError(f"{path}:{lineno}: sections are not supported")
        if "=" not in line:
            raise ConfigError(f"{path}:{lineno}: expected key = value")

        key, raw_value = line.split("=", 1)
        key = key.strip()
        raw_value = raw_value.strip()
        if key not in SUPPORTED_KEYS:
            raise ConfigError(f"{path}:{lineno}: unknown key '{key}'")
        if key in values:
            raise ConfigError(f"{path}:{lineno}: duplicate key '{key}'")
        if not raw_value:
            raise ConfigError(f"{path}:{lineno}: missing value for '{key}'")

        value_type = SUPPORTED_KEYS[key]
        if value_type == "string":
            value = _parse_string(path, lineno, key, raw_value)
        elif value_type == "int":
            value = _parse_int(path, lineno, key, raw_value)
        else:
            value = _parse_bool(path, lineno, key, raw_value)
        values[key] = _validate_value(path, lineno, key, value)
    return values


def _strip_inline_comment(line: str) -> str:
    quote: str | None = None
    escaped = False
    for index, char in enumerate(line):
        if escaped:
            escaped = False
            continue
        if quote == '"' and char == "\\":
            escaped = True
            continue
        if char in {"'", '"'}:
            if quote is None:
                quote = char
            elif quote == char:
                quote = None
            continue
        if char == "#" and quote is None:
            return line[:index]
    return line


def _parse_string(path: Path, lineno: int, key: str, raw_value: str) -> str:
    if not (
        len(raw_value) >= 2
        and raw_value[0] in {"'", '"'}
        and raw_value[-1] == raw_value[0]
    ):
        raise ConfigError(f"{path}:{lineno}: '{key}' must be a quoted string")
    try:
        value = ast.literal_eval(raw_value)
    except (SyntaxError, ValueError) as exc:
        raise ConfigError(f"{path}:{lineno}: invalid string for '{key}'") from exc
    if not isinstance(value, str):
        raise ConfigError(f"{path}:{lineno}: '{key}' must be a quoted string")
    return value


def _parse_bool(path: Path, lineno: int, key: str, raw_value: str) -> bool:
    if raw_value == "true":
        return True
    if raw_value == "false":
        return False
    raise ConfigError(f"{path}:{lineno}: '{key}' must be true or false")


def _parse_int(path: Path, lineno: int, key: str, raw_value: str) -> int:
    try:
        value = int(raw_value, 10)
    except ValueError as exc:
        raise ConfigError(f"{path}:{lineno}: '{key}' must be an integer") from exc
    if str(value) != raw_value:
        raise ConfigError(f"{path}:{lineno}: '{key}' must be an integer")
    return value


def _validate_value(path: Path, lineno: int, key: str, value: object) -> object:
    if key == "privacy_mode" and value not in {"standard", "summary"}:
        raise ConfigError(f"{path}:{lineno}: privacy_mode must be 'standard' or 'summary'")
    if key == "out" and value == "":
        raise ConfigError(f"{path}:{lineno}: out must not be empty")
    if key == "check_dirty" and value not in {"pass", "warn", "block"}:
        raise ConfigError(f"{path}:{lineno}: check_dirty must be 'pass', 'warn', or 'block'")
    if key == "check_max_changed_files" and isinstance(value, int) and value < 0:
        raise ConfigError(f"{path}:{lineno}: check_max_changed_files must be zero or greater")
    return value
