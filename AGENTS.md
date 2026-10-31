# Winnow

Describe what a good robot demonstration looks like in English; Winnow judges every Episode against it, keeps the good ones, routes uncertain ones to a human, and explains every rejection.

- **Intent and plan:** [docs/plan.md](docs/plan.md)
- **Planning map:** [Winnow week build spec](https://github.com/kleongf/winnow/issues/1) (decisions live in its tickets)
- **Vocabulary:** [GLOSSARY.md](GLOSSARY.md). Use its terms in code and prose: Episode, Rubric, Criterion, Criterion result, Triage decision. Never name anything `demo` or `verdict`.

## Verify

```sh
pnpm verify
```

Runs backend and frontend typecheck, lint, format check, and tests; checks the generated API types are current and file sizes are in limits; then boots the app and runs the Playwright e2e tests. Its three parts run alone as `pnpm verify:backend`, `verify:frontend` and `verify:e2e`, which CI runs as parallel jobs.

**Done means** `pnpm verify` passes **and** you have exercised the change in the running app: `pnpm exercise <path> [--click <text>]...` saves screenshots plus console and network errors to `artifacts/exercise/`. Look at the screenshots.

Setup: `pnpm install && uv sync --project backend && pnpm exec playwright install chromium`, plus `ffmpeg` on the PATH; copy `.env.example` to `.env`. Run the app with `pnpm dev` (http://127.0.0.1:5173).

## Conventions

- **Layout:** `backend/` is Python 3.13 (uv, FastAPI, Pydantic, pyright strict, ruff, pytest). `frontend/` is React + strict TypeScript (Vite, TanStack Query, shadcn/ui on Radix with Tailwind, ESLint, Prettier, Vitest); add components with `pnpm dlx shadcn add`, which writes the generated, unlinted `src/components/ui/`. `e2e/` is Playwright; `scripts/` is repo tooling.
- **One directory per feature,** named after the glossary: `backend/src/winnow/<feature>/` with `models.py` (Pydantic types), `service.py` (logic), `routes.py` (FastAPI router, mounted under `/api` in `app.py`); tests in `backend/tests/<feature>/`. The frontend mirrors it in `frontend/src/features/<feature>/`. `core/` holds settings and app-level routes. Create a feature directory when its first code lands.
- **Meta API:** every call goes through `backend/src/winnow/meta/` (auth, retries, rate limits, cost log). Tests and CI never call it; use fixtures.
- **Secrets:** read through `winnow.core.settings`, loaded from `.env`. Never hard-code or log them.
- **Frontend data:** fetch only via TanStack Query hooks that call `frontend/src/api/client.ts`. Its types are generated from the backend's OpenAPI schema: after changing a route or model, run `pnpm gen:api` and commit `schema.ts`. Never hand-write API types. UI state is React local state; no global store.
- **Size limits:** 300 lines per source file (500 for tests), cyclomatic complexity 10. Split by responsibility when you hit them; don't raise the limit.
- **Naming:** Python `snake_case` modules, `PascalCase` models; TS components in `PascalCase.tsx`, everything else `camelCase`.
- **Datasets:** read LeRobot parquet and mp4 directly (pyarrow, ffmpeg); don't depend on the `lerobot` package.
- **e2e Episodes:** all specs share one server whose labels, sets and boxes are permanent, so each spec claims its own fixture Episodes in `EPISODES` (`e2e/helpers.ts`) and ingests, changes and asserts on only those; every spec must pass alone (`playwright test e2e/<file>`).

## Agent skills

### Issue tracker

GitHub Issues on `kleongf/winnow` via the `gh` CLI (sub-issues and native blocking supported). See `docs/agents/issue-tracker.md`.

### Triage labels

The five default roles: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: root `GLOSSARY.md`, ADRs in `docs/adr/` (created when the first one is needed). See `docs/agents/domain.md`.
