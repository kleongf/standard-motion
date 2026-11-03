#!/usr/bin/env bash
# Regenerate frontend/src/api/schema.ts from the backend's OpenAPI schema.
# With --check, fail instead of writing if the committed file is out of date.
set -euo pipefail
cd "$(dirname "$0")/.."

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
uv run --project backend standard-motion-openapi > "$tmp/openapi.json"
pnpm --filter standard-motion-frontend exec openapi-typescript "$tmp/openapi.json" -o "$tmp/schema.ts" > /dev/null

if [[ "${1:-}" == "--check" ]]; then
  if ! diff -q "$tmp/schema.ts" frontend/src/api/schema.ts > /dev/null; then
    echo "frontend/src/api/schema.ts is stale. Run: pnpm gen:api" >&2
    exit 1
  fi
else
  cp "$tmp/schema.ts" frontend/src/api/schema.ts
fi
