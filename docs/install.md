# Install AgentLedger

AgentLedger is source-available for non-commercial use under the PolyForm
Noncommercial License 1.0.0. Install it locally, inspect evidence locally, and
review reports before sharing them.

## From The Current Alpha Tag

Use the tagged alpha when you want the most reproducible public install:

```powershell
python -m pip install "git+https://github.com/Martin123132/AgentLedger.git@v0.1.19-alpha"
python -m agentledger --version
python -m agentledger try
```

## From Latest Master

Use `master` when you want the newest unreleased docs and CLI polish:

```powershell
python -m pip install "git+https://github.com/Martin123132/AgentLedger.git@master"
python -m agentledger --version
python -m agentledger try
```

## From A Development Checkout

Use an editable install when you are changing AgentLedger itself:

```powershell
git clone https://github.com/Martin123132/AgentLedger.git
cd AgentLedger
python -m pip install -e ".[dev]"
python -m pytest
python -m agentledger try
```

## Verify An Install

From a checkout, verify packaging and CLI startup in a temporary virtual
environment:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/install-check.ps1
```

To verify an arbitrary pip source spec, including a local path, wheel, or GitHub
URL:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/install-source-check.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/install-source-check.ps1 -Source "git+https://github.com/Martin123132/AgentLedger.git@v0.1.19-alpha"
```

The source install check creates a temporary virtual environment, installs
AgentLedger from the supplied source, runs `python -m agentledger --version`,
runs `python -m agentledger demo --format json`, and removes the temporary
workspace unless `-KeepTemp` is supplied.

## Uninstall

```powershell
python -m pip uninstall agentledger
```

## After Install

From the repository you want to inspect:

```powershell
python -m agentledger alpha-guide --repo . --out .agentledger
python -m agentledger alpha --repo . --out .agentledger
python -m agentledger status --out .agentledger --allow-warnings
```

Do not commit or upload `.agentledger/`, zip evidence bundles, signing keys, or
full reports unless they have been reviewed and explicitly requested.
