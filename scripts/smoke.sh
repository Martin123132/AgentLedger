#!/usr/bin/env bash
set -euo pipefail

cleanup() {
    rm -rf "$ROOT"
}
trap cleanup EXIT

ROOT="$(mktemp -d)"
REPO="$ROOT/repo"
OUT="$ROOT/ledger"

mkdir -p "$REPO"
mkdir -p "$OUT"
cd "$REPO"

git init -q
git config user.email "agentledger-smoke@example.local"
git config user.name "AgentLedger Smoke"
printf '%s\n' '# Smoke Demo' > README.md
git add README.md
git commit -q -m "initial" > /dev/null

python -m agentledger run \
  --repo "$REPO" \
  --out "$OUT" \
  --no-repomori \
  --no-jester \
  --no-tokometer \
  -- python -c "from pathlib import Path; Path('note.txt').write_text('hello')"

python -m agentledger open-latest --out "$OUT"
python -m agentledger history --out "$OUT"

RUN="$(cat "$OUT/latest.txt" | tr -d '\r\n')"
python -m agentledger inspect-report --format json "$RUN"
python -m agentledger check --allow-warnings "$RUN"
python -m agentledger verify-bundle "${RUN}.zip"

python -m agentledger run \
  --repo "$REPO" \
  --out "$OUT" \
  --no-repomori \
  --no-jester \
  --no-tokometer \
  -- python -c "from pathlib import Path; Path('note.txt').write_text('hello again'); Path('second.txt').write_text('there')"

RUN2="$(cat "$OUT/latest.txt" | tr -d '\r\n')"
python -m agentledger compare --format json "$RUN" "$RUN2"
