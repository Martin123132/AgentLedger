# Public Alpha Recipes

Use these recipes after the safe first look works and you want to point
AgentLedger at a real repository. They are intentionally boring: run one command
through AgentLedger, inspect the latest report, and share only reviewed
snippets.

## Install Once

Use the current checked public alpha tag when you want the reproducible path:

```powershell
python -m pip install "git+https://github.com/Martin123132/AgentLedger.git@v0.1.32-alpha"
python -m agentledger --version
python -m agentledger try
```

`agentledger try` uses a temporary demo repo. It is the safest way to confirm
the install before using a real project.

## Capture Pytest

Use this when the project already has `pytest` available:

```powershell
python -m agentledger run --repo . --out .agentledger -- python -m pytest
python -m agentledger status --out .agentledger --allow-warnings
python -m agentledger open-latest --out .agentledger
```

Open the printed Markdown report first. If the status is `warn`, read the
warning rules before accepting the run.

## Capture Unittest

Use this when you want a standard-library Python test command:

```powershell
python -m agentledger run --repo . --out .agentledger -- python -m unittest discover
python -m agentledger status --out .agentledger --allow-warnings
python -m agentledger history --out .agentledger
```

This is useful for small repositories or first checks where no extra test tool
is installed.

## Capture Npm Test

Use this when the project has an `npm test` script:

```powershell
python -m agentledger run --repo . --out .agentledger -- npm test
python -m agentledger status --out .agentledger --allow-warnings
python -m agentledger review --out .agentledger --allow-warnings
```

AgentLedger labels common test commands, including `npm test`, so the report
can distinguish verification runs from ordinary commands.

## Capture Any Command

Use this for a quick smoke command or a project-specific verification step:

```powershell
python -m agentledger run --repo . --out .agentledger -- python -c "print('hello from AgentLedger')"
python -m agentledger status --out .agentledger --allow-warnings
```

For lower-detail evidence, add `--privacy-mode summary` before the command:

```powershell
python -m agentledger run --repo . --out .agentledger --privacy-mode summary -- python -m pytest
```

Summary mode omits command transcript content and full diffs from reports and
bundles.

## Inspect The Latest Run

After any capture:

```powershell
python -m agentledger open-latest --out .agentledger
python -m agentledger history --out .agentledger --limit 5
$run = (Get-Content .agentledger\latest.txt).Trim()
python -m agentledger inspect-report $run
python -m agentledger check --allow-warnings $run
python -m agentledger verify-bundle "${run}.zip"
```

Use `open-latest` when you only need report paths. Use `inspect-report`,
`check`, and `verify-bundle` when you want a more deliberate review.

## Share Feedback Safely

Use this when you want to paste useful feedback into a GitHub issue, comment,
chat, or email:

```powershell
python -m agentledger support-packet --format markdown
python -m agentledger pack-alpha --out .agentledger
python -m agentledger open-packet --out .agentledger
```

Review the generated Markdown before sharing it. Share only sanitized snippets
from `support-packet --format markdown`, `agentledger-alpha-issue.md`, or a
reviewed public summary.

## Keep Private

Do not paste, upload, commit, screenshot, or attach raw evidence by default:

- raw `.agentledger/` folders
- zip evidence bundles
- command transcripts
- signing keys
- temporary workspaces
- private repo paths
- private URLs
- credentials, tokens, or secrets
- customer data

For the first-run walkthrough, see [first-run.md](first-run.md). For a
public-safe output shape, see
[../examples/sanitized-first-run-output.md](../examples/sanitized-first-run-output.md).
For copy-ready public demo wording, see
[public-demo-script.md](public-demo-script.md).
