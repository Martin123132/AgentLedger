from __future__ import annotations

import re


REDACTED = "[REDACTED]"

_PRIVATE_KEY_RE = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----",
    re.DOTALL,
)
_GITHUB_TOKEN_RE = re.compile(r"\b(gh[opsu]_|github_pat_)[A-Za-z0-9_]{12,}\b")
_OPENAI_KEY_RE = re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b")
_AWS_ACCESS_KEY_RE = re.compile(r"\bAKIA[0-9A-Z]{16}\b")
_BEARER_RE = re.compile(r"(?i)\b(Bearer\s+)[A-Za-z0-9._~+/=-]{8,}")
_URL_PASSWORD_RE = re.compile(r"\b(https?://[^:\s/@]+:)[^@\s/]+@")
_JSON_SECRET_RE = re.compile(
    r'(?i)("?[A-Za-z0-9_.-]*(?:api[_-]?key|token|secret|password|passwd|pwd|authorization)"?\s*:\s*")([^"\r\n]+)(")'
)
_ASSIGNMENT_SECRET_RE = re.compile(
    r"(?i)\b([A-Za-z0-9_.-]*(?:api[_-]?key|token|secret|password|passwd|pwd|authorization)[A-Za-z0-9_.-]*\s*=\s*)([^\s'\";]+)"
)
_FLAG_ASSIGNMENT_RE = re.compile(
    r"(?i)^(-{1,2}(?:api[-_]?key|token|secret|password|passwd|pwd|authorization)=).+"
)
_SENSITIVE_FLAG_RE = re.compile(
    r"(?i)^-{1,2}(?:api[-_]?key|token|secret|password|passwd|pwd|authorization)$"
)


def redact_text(text: str | None) -> str:
    if not text:
        return ""
    redacted = _PRIVATE_KEY_RE.sub("[REDACTED PRIVATE KEY]", text)
    redacted = _GITHUB_TOKEN_RE.sub(lambda match: f"{match.group(1)}{REDACTED}", redacted)
    redacted = _OPENAI_KEY_RE.sub(f"sk-{REDACTED}", redacted)
    redacted = _AWS_ACCESS_KEY_RE.sub(f"AKIA{REDACTED}", redacted)
    redacted = _BEARER_RE.sub(lambda match: f"{match.group(1)}{REDACTED}", redacted)
    redacted = _URL_PASSWORD_RE.sub(lambda match: f"{match.group(1)}{REDACTED}@", redacted)
    redacted = _JSON_SECRET_RE.sub(lambda match: f"{match.group(1)}{REDACTED}{match.group(3)}", redacted)
    return _ASSIGNMENT_SECRET_RE.sub(lambda match: f"{match.group(1)}{REDACTED}", redacted)


def redact_command(command: list[str]) -> list[str]:
    redacted: list[str] = []
    redact_next = False
    for item in command:
        if redact_next:
            redacted.append(REDACTED)
            redact_next = False
            continue
        flag_assignment = _FLAG_ASSIGNMENT_RE.match(item)
        if flag_assignment:
            redacted.append(f"{flag_assignment.group(1)}{REDACTED}")
            continue
        redacted.append(redact_text(item))
        if _SENSITIVE_FLAG_RE.match(item):
            redact_next = True
    return redacted
