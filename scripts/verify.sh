#!/usr/bin/env bash
# `pnpm verify`: the one command that says whether the repo is healthy. It runs three parts,
# which CI runs as parallel jobs: `pnpm verify:backend`, `pnpm verify:frontend` (which also
# checks the scripts, the generated API types and file sizes) and `pnpm verify:e2e`.
set -euo pipefail
cd "$(dirname "$0")/.."

step() { printf '\n\033[1m▶ %s\033[0m\n' "$1"; }

backend() {
  step "backend: format, lint, types, tests"
  (cd backend && uv run ruff format --check . && uv run ruff check . && uv run pyright && uv run pytest)
}

frontend() {
  step "frontend: types, lint, format, tests"
  pnpm --filter winnow-frontend run typecheck
  pnpm --filter winnow-frontend run lint
  pnpm --filter winnow-frontend run format:check
  pnpm --filter winnow-frontend run test

  step "scripts and e2e: types, format"
  pnpm exec tsc -p tsconfig.json
  pnpm exec prettier --check scripts e2e playwright.config.ts

  step "generated API types are current"
  bash scripts/gen-api.sh --check

  step "file size limits"
  python3 scripts/check_file_size.py
}

e2e() {
  step "e2e: boot the app and click through it"
  pnpm exec playwright test
}

part="${1:-all}"
case "$part" in
  backend) backend ;;
  frontend) frontend ;;
  e2e) e2e ;;
  all)  # separate commands: errexit doesn't apply inside a function called from an && list
    backend
    frontend
    e2e
    ;;
  *)
    echo "usage: scripts/verify.sh [backend|frontend|e2e]" >&2
    exit 2
    ;;
esac

label="${part/#all/}"
printf '\n\033[1;32m✔ verify%s passed\033[0m\n' "${label:+ $label}"
