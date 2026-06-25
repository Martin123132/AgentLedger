# Public Alpha Trial

Use this short loop when you want to try the current public alpha and send
useful feedback without sharing raw evidence.

## Install

```powershell
python -m pip install "git+https://github.com/Martin123132/AgentLedger.git@v0.1.25-alpha"
python -m agentledger --version
```

Expected version:

```text
agentledger 0.1.25a0
```

## Safe First Run

```powershell
python -m agentledger try
```

Read the printed Markdown report first. Then review the generated
`agentledger-alpha-issue.md` draft before copying anything into GitHub, X, chat,
or email.

## Support Packet

When reporting a problem or confusing output, generate the copy-ready support
body:

```powershell
python -m agentledger support-packet --format markdown
```

Paste only reviewed, sanitized snippets. Include:

- command used
- install method and AgentLedger version
- platform, shell, and Python version
- the generated review/share filenames after review
- redacted error text or the first confusing message
- what you expected and what happened instead

## Keep Private

Do not paste, upload, or commit:

- raw `.agentledger/` evidence folders
- zip evidence bundles
- command transcripts
- signing keys
- temp workspaces
- private repo paths
- private URLs
- credentials, tokens, or secrets
- customer data

## Real Repository Trial

After the safe demo makes sense, move into a repository you control:

```powershell
cd D:\Projects\your-repo
python -m agentledger alpha-guide --repo . --out .agentledger
```

The public license allows non-commercial use under `LICENSE`. Commercial use
requires separate written permission; see `COMMERCIAL.md` and
`COMMERCIAL-LICENSE.md`.
