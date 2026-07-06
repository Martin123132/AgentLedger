# AgentLedger Receipt Command

`agentledger receipt` is the commercial pilot workflow for one AI-assisted
repository task.

It wraps the existing AgentLedger evidence loop into one command that a team can
run after an agent, assistant, or scripted workflow changes a repo:

```powershell
python -m agentledger receipt --repo . --out .agentledger -- python -m pytest
```

For a commercial pilot, write a preset first:

```powershell
python -m agentledger init-config --repo . --preset client-handoff
python -m agentledger receipt --repo . -- python -m pytest
```

The command:

1. checks local readiness with the same doctor rules used by alpha flows
2. captures before/after git state around the requested command
3. writes the normal Markdown, JSON, and HTML evidence reports
4. writes `agentledger-receipt.md`, `agentledger-receipt.json`, and
   `agentledger-receipt.html`
5. regenerates the zip evidence bundle so the receipt files are included
6. optionally signs the bundle with a shared HMAC key
7. verifies the final bundle

## Receipt Status

Receipts use a buyer-facing acceptance label:

- `ready`: the captured run passed policy checks and the bundle verified
- `review`: the run has warnings, but strict mode was not requested
- `blocked`: setup, capture, policy, signing, or bundle verification failed

Use `--strict` when warnings should return a nonzero exit code:

```powershell
python -m agentledger receipt --strict --repo . --out .agentledger -- npm test
```

## Signing

For customer pilots that need tamper-evident local handoff, pass a shared key
file:

```powershell
python -m agentledger receipt --repo . --out .agentledger --signature-key-file .agentledger-signing-key -- python -m pytest
```

Check key hygiene before using a repo-local key:

```powershell
python -m agentledger signing-key --repo . --key-file .agentledger-signing-key
```

The signature is an HMAC-SHA256 check over the bundle manifest. It is not a
public-key signature.

## JSON Contract

Machine consumers should use:

```powershell
python -m agentledger receipt --format json --repo . --out .agentledger -- python -m pytest
```

The payload uses `agentledger.receipt.v1` and includes:

- command and capture exit status
- policy status and warnings/blockers
- evidence report paths
- receipt file paths
- optional integration summaries
- final bundle verification payload
- optional signing payload
- handling reminders and next actions

See [json-contracts.md](json-contracts.md) for the stable fields.

## Evidence Handling

Receipt Markdown and HTML are the first files to review. The zip evidence bundle
is private by default because it can include command transcripts, diffs, local
paths, and optional integration artifacts.

Share the receipt first. Share the zip bundle only when a reviewer needs raw
evidence and the contents have been checked.
