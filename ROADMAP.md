# AgentLedger Roadmap

## Goal

Build the first public alpha of a local-first agent control product:

```text
Track agent spend. Capture repo state. Prove what changed. Export audit
evidence. Gate risky outputs.
```

## Build Order

1. CLI evidence loop
2. Markdown/JSON/HTML reports
3. command transcripts and test-command detection
4. `doctor` readiness checks
5. RepoMori before/after snapshots
6. Jester safety gate
7. bounded Tokometer usage summaries
8. zip evidence bundle
9. Marked Bench eval gate
10. signed evidence records
11. desktop dashboard

## Buyer-Facing MVP

The first pilot should answer:

- What did the agent run?
- What files changed?
- What did the diff contain?
- Did tests run?
- Did safety/eval gates pass?
- How much agent usage happened nearby?
- Can another person or agent reproduce the evidence?

The current MVP command is:

```powershell
agentledger receipt --repo . --out .agentledger -- python -m pytest
```

It turns one captured run into a receipt pack, verifies the evidence bundle, and
optionally signs the bundle for local handoff. See `docs/receipt.md` and
`docs/commercial-mvp.md`.

## Non-Goals For The First Cut

- hosted SaaS
- multi-tenant auth
- new AI model
- full agent runtime
- replacing Tokometer, RepoMori, Jester, or Marked Bench internals

AgentLedger coordinates them first. It absorbs internals only when a repeated
integration becomes stable enough to justify it.
