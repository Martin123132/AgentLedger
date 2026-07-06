# Commercial MVP Plan

## Product Wedge

AgentLedger is the local-first run receipt layer for teams using AI coding
agents and shell-based automation.

The first sellable promise is narrow:

```text
Show what the agent ran, what changed, what evidence exists, and whether the
bundle can be trusted.
```

The commercial MVP is not a hosted agent platform, model runtime, or SaaS
dashboard. It is a practical accountability layer that works beside Codex,
Claude Code, Cursor, OpenAI Agents SDK scripts, and ordinary shell workflows.

## Serious Repo Inputs

The fastest build path keeps AgentLedger as the wrapper product and treats the
adjacent serious repos as integration or product-design inputs:

- AgentLedger: run capture, git state, reports, bundles, policy checks, signing
- RepoMori: repo-memory snapshots and future handoff capsules
- Tokometer: bounded local Codex usage summaries and burn-rate evidence
- Sentinel/ManifoldGuard: release-gate posture and pass/warn/block language
- The Marked Bench: eval result-card discipline and versioned evidence thinking

This MVP does not copy those internals. It exposes a clean receipt workflow
first, then deepens integrations when pilot users prove which evidence they
actually need.

## Demo Flow

From a checkout:

```powershell
python -m pip install -e ".[dev]"
python -m agentledger init-config --repo . --preset client-handoff
python -m agentledger receipt --repo . --out .agentledger -- python -m pytest
python -m agentledger status --out .agentledger --allow-warnings
python -m agentledger open-latest --out .agentledger
```

For a safer first customer demo, use summary privacy mode:

```powershell
python -m agentledger receipt --repo . --out .agentledger --privacy-mode summary -- python -m pytest
```

For tamper-evident local handoff:

```powershell
python -m agentledger signing-key --repo . --key-file .agentledger-signing-key
python -m agentledger receipt --repo . --out .agentledger --signature-key-file .agentledger-signing-key -- python -m pytest
```

The reviewer opens:

```text
.agentledger/<run-id>/agentledger-receipt.md
.agentledger/<run-id>/agentledger-receipt.html
.agentledger/<run-id>/agentledger-report.md
.agentledger/<run-id>.zip
```

## Packaging Notes

Pilot packaging should stay boring:

- publish a tagged Python package from this repo
- keep the CLI dependency-light
- ship the source install path first:

```powershell
python -m pip install "git+https://github.com/Martin123132/AgentLedger.git@<tag>"
```

- keep local evidence under `.agentledger/`
- keep `.agentledger/`, `*.zip`, and signing keys ignored by default
- document Windows PowerShell examples first, then Linux/macOS shell examples
- avoid hosted storage until pilots prove the exact trust model

The receipt command is the packaging anchor because it has one memorable job and
one output family.

## Buyer Pilot

The first buyer profile is a team or consultant already using AI coding agents
and needing proof for review, handoff, or client trust.

Pilot checklist:

- one installation command
- one receipt command
- one demo repo task
- one policy config
- one reviewed receipt packet
- one support channel for friction reports

Pilot success looks like:

- a non-expert can find the receipt and bundle
- a reviewer can tell whether tests ran
- a manager can see changed-file count and warning status
- a technical reviewer can verify the bundle
- the team can keep raw evidence private by default

## Next Commercialization Steps

1. Package `agentledger receipt` as the default first-run flow.
2. Add a short customer-facing demo video or screenshot walkthrough.
3. Create a commercial license quote sheet for teams and agencies.
4. Add a tiny receipt index command for browsing local receipts by status.
5. Deepen optional integrations only when a pilot asks for them twice.
6. Build a desktop dashboard after the CLI proves the repeated workflow.

## Non-Goals

- no hosted SaaS in the first MVP
- no multi-tenant auth
- no new AI model
- no replacement for agent runtimes
- no speculative research pitch
- no raw evidence upload by default
