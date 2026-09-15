#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 || $# -gt 2 ]]; then
  echo "Usage: $0 <payload.json> [engine-url]" >&2
  echo "Example: NOTIFY_AUTH_TOKEN=... $0 tests/testdata/fomc-sept-2026/fomc-2026-09-16-surprise-hold-dovish-positive.json http://localhost:8000" >&2
  exit 2
fi

payload_file="$1"
engine_url="${2:-${TRADE_ENGINE_URL:-http://localhost:8000}}"

if [[ ! -f "$payload_file" ]]; then
  echo "Payload file not found: $payload_file" >&2
  exit 2
fi

if [[ -z "${NOTIFY_AUTH_TOKEN:-}" ]]; then
  echo "NOTIFY_AUTH_TOKEN is required." >&2
  exit 2
fi

curl -sS -X POST "${engine_url%/}/notify/web-monitor" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${NOTIFY_AUTH_TOKEN}" \
  --data-binary "@${payload_file}"
