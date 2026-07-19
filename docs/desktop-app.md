# AgentLedger Desktop

AgentLedger Desktop is a Windows application layer over the existing local CLI
engine. The desktop does not implement a second recorder: capture, policy,
redaction, report history, and chain verification continue to use the same
AgentLedger Python modules and JSON contracts.

## Run From Source

```powershell
python -m pip install -e ".[dev]"
python -m agentledger.desktop
```

The installed Python package also exposes `agentledger-desktop`.

## Build The Windows Package

Use a temporary virtual environment on a drive with enough space, install the
desktop build extra, and run the checked build script:

```powershell
$env:TEMP = "D:\Temp"
$env:TMP = "D:\Temp"
python -m venv D:\Temp\agentledger-desktop-build-venv
D:\Temp\agentledger-desktop-build-venv\Scripts\python.exe -m pip install -e ".[desktop]"
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/build-desktop.ps1 -Python D:\Temp\agentledger-desktop-build-venv\Scripts\python.exe
```

The full installer build requires Inno Setup 6. Pass `-SkipInstaller` for a
portable-only local build. Generated output is written under `dist/desktop/`
and ignored by git:

- `AgentLedger.exe`
- `AgentLedger-<version>-windows-x64-portable.zip`
- `AgentLedger-<version>-windows-x64-setup.exe`
- `agentledger-desktop-manifest.json`
- `LICENSE`
- `COMMERCIAL.md`

The setup installs per user under `%LOCALAPPDATA%\Programs\AgentLedger`, adds a
Start menu shortcut and uninstaller, and does not require administrator access.

## App Store Handoff

`agentledger-desktop-manifest.json` uses
`agentledger.desktop_package.v1`. It records the stable app ID, version,
channel, platform, architecture, install scope, entrypoint, license contact,
privacy defaults, source commit, filenames, sizes, and SHA-256 hashes. It is a
generic producer manifest so a store can adapt it without AgentLedger depending
on an unfinished store-specific schema.

The GitHub Desktop Build workflow checks relevant pull requests and `master`.
For future published releases it also attaches the executable, portable zip,
installer, manifest, and license files to the matching GitHub release.

## Privacy And Signing

The desktop preserves AgentLedger's local-first behavior. Raw `.agentledger/`
evidence, bundles, transcripts, repository paths, and signing keys are not sent
to GitHub or an app store by the application.

Current alpha installers are unsigned and may trigger Windows SmartScreen.
Production distribution should add Authenticode signing in a protected release
job; signing credentials must never be committed or exposed to pull requests.
