#!/usr/bin/env bash
set -euo pipefail

cleanup() {
    rm -rf "$ROOT"
}
trap cleanup EXIT

ROOT="$(mktemp -d)"
REPO="$ROOT/repo"
OUT="$ROOT/ledger"
SIGNATURE_KEY="$ROOT/agentledger-signing-key.txt"
FEEDBACK_EXPORT_MD="$ROOT/agentledger-feedback.md"
FEEDBACK_EXPORT_JSON="$ROOT/agentledger-feedback.json"

mkdir -p "$REPO"
mkdir -p "$OUT"
printf '%s\n' 'agentledger-smoke-signing-key' > "$SIGNATURE_KEY"
cd "$REPO"

git init -q
git config user.email "agentledger-smoke@example.local"
git config user.name "AgentLedger Smoke"
printf '%s\n' '# Smoke Demo' > README.md
git add README.md
git commit -q -m "initial" > /dev/null

python -m agentledger contracts
python -m agentledger contracts --format json

python -m agentledger run \
  --repo "$REPO" \
  --out "$OUT" \
  --no-repomori \
  --no-jester \
  --no-tokometer \
  -- python -c "from pathlib import Path; Path('note.txt').write_text('hello')"

python -m agentledger open-latest --out "$OUT"
python -m agentledger open-latest --format json --out "$OUT"
python -m agentledger history --out "$OUT"
python -m agentledger feedback --out "$OUT" --note "Smoke feedback note." --category friction --severity low
python -m agentledger feedback --out "$OUT" --list
python -m agentledger feedback --format json --out "$OUT" --list
python -m agentledger feedback-summary --out "$OUT"
python -m agentledger feedback-summary --format json --out "$OUT"
python -m agentledger feedback-export --out "$OUT" --output "$FEEDBACK_EXPORT_MD"
python -m agentledger feedback-export --format json --out "$OUT" --output "$FEEDBACK_EXPORT_JSON" --output-format json

RUN="$(cat "$OUT/latest.txt" | tr -d '\r\n')"
python -m agentledger inspect-report --format json "$RUN"
python -m agentledger check --allow-warnings "$RUN"
python -m agentledger review --out "$OUT" --allow-warnings
python -m agentledger review --format json --out "$OUT" --allow-warnings
CHECK_JSON="$ROOT/agentledger-check.json"
set +e
python -m agentledger check --format json --allow-warnings "$RUN" > "$CHECK_JSON"
CHECK_STATUS=$?
set -e
if [ "$CHECK_STATUS" -ne 0 ]; then
  echo "agentledger check --format json exited with code $CHECK_STATUS" >&2
  exit "$CHECK_STATUS"
fi
python - "$CHECK_JSON" <<'PY'
import json
import sys

payload = json.load(open(sys.argv[1], encoding="utf-8-sig"))
required = {
    "schema_version",
    "status",
    "ok",
    "summary",
    "rule_counts",
    "warning_rules",
    "blocking_rules",
    "rules",
}
missing = sorted(required - payload.keys())
if missing:
    raise SystemExit(f"Missing check JSON fields: {', '.join(missing)}")
if payload["schema_version"] != "agentledger.check.v1":
    raise SystemExit(f"Unexpected check schema: {payload['schema_version']}")
if payload["status"] not in {"pass", "warn"}:
    raise SystemExit(f"Unexpected smoke check status: {payload['status']}")
counts = payload["rule_counts"]
if counts["total"] != len(payload["rules"]):
    raise SystemExit("rule_counts.total does not match rules length")
if counts["warn"] != len(payload["warning_rules"]):
    raise SystemExit("rule_counts.warn does not match warning_rules length")
if counts["block"] != len(payload["blocking_rules"]):
    raise SystemExit("rule_counts.block does not match blocking_rules length")
print(f"AgentLedger check JSON: {payload['status']} - {payload['summary']}")
PY
python -m agentledger verify-bundle "${RUN}.zip"
python -m agentledger verify-bundle "${RUN}.zip" --format json
python -m agentledger sign-bundle "${RUN}.zip" --key-file "$SIGNATURE_KEY"
python -m agentledger verify-bundle "${RUN}.zip" --signature-key-file "$SIGNATURE_KEY"
python -m agentledger verify-bundle "${RUN}.zip" --format json --signature-key-file "$SIGNATURE_KEY"

python -m agentledger run \
  --repo "$REPO" \
  --out "$OUT" \
  --no-repomori \
  --no-jester \
  --no-tokometer \
  -- python -c "from pathlib import Path; Path('note.txt').write_text('hello again'); Path('second.txt').write_text('there')"

RUN2="$(cat "$OUT/latest.txt" | tr -d '\r\n')"
python -m agentledger compare --format json "$RUN" "$RUN2"
