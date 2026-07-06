# Policy Presets

Policy presets write a starter `.agentledger.toml` for the way a team wants to
review AI-assisted work.

```powershell
python -m agentledger init-config --repo . --preset solo
python -m agentledger init-config --repo . --preset agency
python -m agentledger init-config --repo . --preset team-strict
python -m agentledger init-config --repo . --preset client-handoff
```

Use `--force` to replace an existing config after reviewing it:

```powershell
python -m agentledger init-config --repo . --preset client-handoff --force
```

## Presets

| Preset | Use when | Policy shape |
| --- | --- | --- |
| `solo` | One person wants useful receipts without blocking on every warning. | Summary privacy, tests required, dirty state warns, warnings allowed. |
| `agency` | A consultant or agency needs delivery evidence before client handoff. | Summary privacy, tests required, tighter changed-file limit, warnings exit nonzero. |
| `team-strict` | A team wants receipts to fail until the final repo state is clean. | Summary privacy, tests required, dirty state blocks, warnings exit nonzero. |
| `client-handoff` | A receipt may be reviewed outside the delivery machine. | Summary privacy, tests required, tighter changed-file limit, warnings exit nonzero. |

## Recommended First Run

For most commercial pilots:

```powershell
python -m agentledger init-config --repo . --preset client-handoff
python -m agentledger receipt --repo . -- python -m pytest
```

If the receipt warns or blocks, read `agentledger-receipt.md` first, then the
full Markdown evidence report.
