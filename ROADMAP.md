# AgentLedger Roadmap

## Goal

Build the first private version of a local-first agent control product:

```text
Track agent spend. Capture repo state. Prove what changed. Export audit
evidence. Gate risky outputs.
```

## Build Order

1. CLI evidence loop
2. Markdown/JSON reports
3. RepoMori before/after snapshots
4. Jester safety gate
5. bounded Tokometer usage summaries
6. HTML report and zip bundle
7. Marked Bench eval gate
8. signed evidence records
9. desktop dashboard

## Buyer-Facing MVP

The first pilot should answer:

- What did the agent run?
- What files changed?
- What did the diff contain?
- Did tests run?
- Did safety/eval gates pass?
- How much agent usage happened nearby?
- Can another person or agent reproduce the evidence?

## Non-Goals For The First Cut

- hosted SaaS
- multi-tenant auth
- new AI model
- full agent runtime
- replacing Tokometer, RepoMori, Jester, or Marked Bench internals

AgentLedger coordinates them first. It absorbs internals only when a repeated
integration becomes stable enough to justify it.
