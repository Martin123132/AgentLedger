from __future__ import annotations


def detect_test_command(command: list[str]) -> tuple[bool, str | None]:
    lowered = [part.lower() for part in command]
    joined = " ".join(lowered)
    if not command:
        return False, None
    if "pytest" in lowered or "python -m pytest" in joined:
        return True, "pytest"
    if "vitest" in lowered or "vitest" in joined:
        return True, "vitest"
    if "jest" in lowered or "jest" in joined:
        return True, "jest"
    if "npm" in lowered and "test" in lowered:
        return True, "npm test"
    if "pnpm" in lowered and "test" in lowered:
        return True, "pnpm test"
    if "yarn" in lowered and "test" in lowered:
        return True, "yarn test"
    if "unittest" in joined:
        return True, "unittest"
    if "go" in lowered and "test" in lowered:
        return True, "go test"
    if "cargo" in lowered and "test" in lowered:
        return True, "cargo test"
    return False, None
