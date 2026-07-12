# Alpha Tester Guide

AgentLedger is a local-first evidence recorder for AI coding-agent work. This alpha is checking the core loop: install, run a command under AgentLedger, inspect the evidence, and report where the experience feels unclear.

## What you need

- Python 3.12 or newer
- Git available in your shell
- Access to an AgentLedger checkout
- Windows PowerShell if you use the extended script

If PowerShell cannot find `git`, let AgentLedger locate a common Git install for the current session:

```powershell
. .\scripts\ensure-git.ps1
```

## Setup

From the repository root:

```powershell
python -m pip install -e ".[dev]"
agentledger --version
python -m agentledger try
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/install-check.ps1
python -m agentledger doctor --repo . --format markdown
python -m agentledger alpha-guide --repo . --out .agentledger
```

Expected result:

- `agentledger --version` prints the installed AgentLedger version
- `agentledger try` creates an isolated temporary demo repo, prints report,
  bundle, and packet handoff paths, labels what to review/share versus keep
  local, and gives a cleanup command
- `scripts/install-check.ps1` installs AgentLedger into a temporary environment,
  prints each verification step, checks both CLI entry points, and cleans up
- `doctor` should say `ready` when required checks pass
- If `doctor` reports a missing check, read the `Hint:` line directly below it
- `doctor --format markdown` should be copy-ready, path-redacted, and should
  say `Local paths included: no`
- `alpha-guide` shows doctor readiness, optional integration counts, install
  verification commands, the command loop, troubleshooting steps, evidence
  paths, and privacy reminders
- Missing RepoMori, Jester, or Tokometer warnings are OK for this alpha

See [demo.md](demo.md) when you want the expected demo output before running
the full alpha pass.

## Troubleshooting

Use [alpha-troubleshooting.md](alpha-troubleshooting.md) or rerun:

```powershell
python -m agentledger alpha-guide --repo . --out .agentledger
```

Use the guide to separate:

- install problems: run `python -m agentledger doctor --repo .` and read any `Hint:` lines
- command problems: run `python -m agentledger alpha-summary --out .agentledger` and `python -m agentledger status --out .agentledger --allow-warnings`
- packet confusion: run `python -m agentledger open-packet --out .agentledger`
- privacy-safe reporting: share reviewed packet/export text, not raw evidence

## One-command alpha pass

Run:

```powershell
python -m agentledger alpha-guide --repo . --out .agentledger
python -m agentledger alpha --repo . --out .agentledger
```

Windows users can also run the extended script:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/alpha.ps1
```

Expected result:

- doctor passes
- a real pytest run is captured under `.agentledger/`
- `status` summarizes the latest captured run
- latest/history/inspect/check/verify commands all succeed
- a short summary is printed to send back
- blocked runs include a `Fix first:` section before the detailed error list
- blocked setup in `alpha-guide` includes the same `Fix first:` repair actions
  before you run the alpha pass
- `.agentledger/alpha-summary.json` records the same alpha pass for tools or
  agent handoffs
- the Windows script also runs install and smoke checks

Inspect the saved summary:

```powershell
python -m agentledger alpha-summary --out .agentledger
python -m agentledger alpha-summary --out .agentledger --format json
```

## Smoke test

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/install-check.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/smoke.ps1
```

Expected result:

- Both scripts exit successfully
- Smoke output shows a report folder and zip bundle
- Temporary smoke output stays under a temp folder

## Real capture

Run AgentLedger against the test suite:

```powershell
python -m agentledger run --repo . --out .agentledger --no-repomori --no-jester --no-tokometer -- python -m pytest
```

Inspect the run:

```powershell
python -m agentledger open-latest --out .agentledger
python -m agentledger open-latest --format json --out .agentledger
python -m agentledger history --out .agentledger
python -m agentledger review --out .agentledger --allow-warnings
python -m agentledger review --format markdown --out .agentledger --allow-warnings --output $env:TEMP\agentledger-review.md
python -m agentledger status --out .agentledger --allow-warnings
python -m agentledger feedback --out .agentledger --note "First confusing thing: ..."
python -m agentledger feedback --out .agentledger --list
python -m agentledger feedback-summary --out .agentledger
python -m agentledger feedback-export --out .agentledger --output $env:TEMP\agentledger-feedback.md
python -m agentledger support-packet
python -m agentledger support-packet --format markdown
python -m agentledger support-packet --format json
python -m agentledger alpha-handoff --out .agentledger --output-dir $env:TEMP\agentledger-alpha-handoff
python -m agentledger alpha-handoff --out .agentledger --output-dir $env:TEMP\agentledger-alpha-handoff-safe --share-safe
python -m agentledger pack-alpha --out .agentledger
python -m agentledger open-packet --out .agentledger
$run = (Get-Content .agentledger\latest.txt).Trim()
python -m agentledger inspect-report $run
python -m agentledger check --repo . $run
python -m agentledger inspect-bundle "$run.zip"
python -m agentledger inspect-bundle "$run.zip" --format json
python -m agentledger verify-bundle "$run.zip"
python -m agentledger verify-bundle "$run.zip" --format json
```

Expected result:

- The captured command exits with code `0`
- `history` shows the pytest run
- `review` prints the latest report paths, pass/warn/block policy status, recent run context, and previous-run comparison when available
- `review --format markdown --output <path>` writes a compact review handoff file without copying raw `.agentledger` evidence
- `status` rolls latest run policy, report-chain health, evidence paths, feedback counts, and next action into one view
- `feedback` records local notes in the latest run folder and lists them back
- `feedback-summary` rolls local notes up across run folders
- `feedback-export` writes a reviewed Markdown or JSON feedback handoff without local evidence paths
- `support-packet --format markdown` prints a copy-ready issue/comment body without writing files, copying evidence, or including local paths by default
- `alpha-handoff --share-safe` writes a compact Markdown/JSON handoff packet without copying raw evidence or exposing local absolute paths
- `pack-alpha` validates the share-safe packet, writes `agentledger-alpha-issue.md` as a copy-ready GitHub issue/comment draft, and includes a `Sharing` section with keep-private reminders plus `public_summary` snippets for short updates
- `pack-alpha` defaults to a fresh temporary packet directory; pass `--output-dir` when you want a predictable folder
- `open-packet` reprints the latest packet paths from `.agentledger/latest-alpha-packet.json`
- `inspect-report` summarizes command, exit code, test framework, changed files, and artifacts
- `check` evaluates the run using `.agentledger.toml`
- `inspect-bundle` summarizes manifest, signature presence, reports, command outcome, and pass/warn/block review status without needing a signing key
- `verify-bundle` prints `Bundle OK` after validating the bundle manifest and checksums
- `review --format json`, `status --format json`, `open-latest --format json`, `open-packet --format json`, `inspect-bundle --format json`, and `verify-bundle --format json` produce machine-readable status for CI or agent handoffs
- Optional: `signing-key` checks shared-key file hygiene before `sign-bundle` adds an HMAC signature that `verify-bundle --signature-key-file --require-signature` can verify

## Evidence location

AgentLedger writes local evidence under:

```text
.agentledger/
```

Each run includes:

- `agentledger-report.md`
- `agentledger-report.json`
- `agentledger-report.html`
- `alpha-feedback.jsonl` if you recorded feedback for that run
- `artifacts/`
- a sibling `.zip` bundle with `agentledger-bundle-manifest.json`

Do not commit `.agentledger/`, zip bundles, signing keys, logs, screenshots, or sensitive evidence.
Only share feedback exports or alpha handoff packets after reviewing their notes.

## Feedback focus

Please report:

- the command used, starting with `python -m agentledger try` if you ran the safe first-run path
- OS/platform, shell, Python version, and AgentLedger version
- generated review/share files you reviewed, especially `agentledger-alpha-issue.md`, `agentledger-alpha-handoff.md`, and `agentledger-alpha-handoff.json`
- the first command that felt confusing
- any command that failed and the redacted error text
- whether the report was understandable
- whether the status/latest/history/inspect/check/verify flow made sense
- whether anything looked unsafe to share or too noisy

Use `docs/alpha-feedback-template.md` for notes, or
`.github/ISSUE_TEMPLATE/alpha-feedback.md` when opening an alpha feedback issue.
Run `agentledger support-packet` when you want the checklist before posting, or
`agentledger support-packet --format markdown` when you want a copy-ready
issue/comment body.
Paste only reviewed packet/export text. Keep raw `.agentledger/` evidence, zip
bundles, command transcripts, signing keys, temporary demo workspaces, secrets,
and non-public source private by default.
