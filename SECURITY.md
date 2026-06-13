# Security Policy

AgentLedger is a local-first alpha tool. It writes evidence to local folders such
as `.agentledger/` and may capture command output, file paths, git status, diffs,
and integration summaries.

AgentLedger applies best-effort redaction for common token, password, API key,
authorization header, and private-key patterns before writing reports and command
transcripts. This is a safety net, not a guarantee.

Use `--privacy-mode summary` for lower-detail evidence. Summary mode keeps
metadata and counts but omits command transcript content and full diffs from the
generated reports and bundles.

Repos can set `privacy_mode = "summary"` or `zip = false` in
`.agentledger.toml` when lower-detail local defaults are safer for day-to-day
work. Command-line flags still override privacy and output choices for a single
run.

## Supported Versions

Only the current `master` branch is supported during the public alpha.

## Reporting A Security Issue

Do not open a public issue that contains secrets, non-public source code, evidence
bundles, or full `.agentledger/` output.

If you find a security issue, use GitHub's private vulnerability reporting if it
is available for this repository. Otherwise, open a minimal public issue that
describes the affected area without including sensitive data.

## Evidence Safety

- Do not commit `.agentledger/` folders.
- Do not commit zip evidence bundles.
- Review reports before sharing them outside your machine.
- Assume command transcripts can contain sensitive output from the command you
  asked AgentLedger to run.
- Assume unusual or project-specific credentials may need manual review even
  when common secret patterns are redacted.
- Use `--privacy-mode summary` before sharing evidence outside your machine when
  full diffs or command output are not needed.
- Consider a repo `.agentledger.toml` for safer default capture behavior before
  alpha testing or sharing evidence.
- Rotate any credential that appears in a generated report or bundle.
