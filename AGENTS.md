# AGENTS.md — rules for every coding agent run

Read this file and `prompts/AGENT_RULES.md` before you change anything. The approved design is `docs/02-design.md`; requirements are `docs/01-requirements-spec.md`; the run plan is `docs/03-sprint-plan.md`. When this file and the design disagree, the design wins for behaviour, this file wins for process.

## Product
Procurement Document Assistant for a fictional UAE company ("Demo Holdings LLC"). Staff upload quotes, POs, delivery notes and invoices; AI extracts fields; plain code does comparison, three-way match, approvals, RBAC and the audit trail. All data is synthetic, money is AED.

## Stack
- Backend: Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2 (typed, `Mapped[]`), Alembic, psycopg 3, Postgres 16 + pgvector. `api` and `worker` share one codebase with two entry points.
- Frontend: Next.js (App Router), TypeScript, Tailwind (from R05).
- Storage: Azure Blob (Azurite locally). AI: Azure OpenAI + Azure Document Intelligence, **always behind the `ai` module interface; local/CI use mock or replay providers only**.
- Tooling: `uv` for Python deps, `ruff` (lint + format), `mypy --strict` on `app/`, `pytest`. Docker Compose for local stack. GitHub Actions CI.

## Layout and folder ownership
```
apps/web/                     Next.js app (R05+)
services/backend/
  pyproject.toml
  app/
    core/        config, db session, security (JWT, passwords), RBAC policy, errors, request id  (R01)
    audit/       audit.record(), hash chain, audit API + CSV export                                 (R01)
    integrations/ adapter interfaces + mocks: odoo, sharepoint, power_automate, identity          (R02)
    ai/          the ONLY module that may call Azure OpenAI / Document Intelligence               (R03)
    documents/ extraction/ worker/                                                                (R03)
    approvals/ comparison/ matching/ orders/                                                      (R04)
    qa/                                                                                           (R07)
    main.py      api entry point;  worker_main.py worker entry point                              (R01)
  migrations/    Alembic (R01 owns; the full schema of design 4.3 is created in R01)
  tests/{unit,integration,security}/
seed/            master data + loader (R02)       tools/datagen/  synthetic document generator (R02)
eval/data/       evaluation set + replay fixtures (R02)       e2e/  Playwright (R11)
infra/           Bicep + scripts (R06)            prompts/  task prompts for agent runs
docs/            phase documents
```
Only edit folders your run owns (see your prompt). If you truly need a change elsewhere, keep it minimal and list it in your final report.

## Commands (must work from the repo root)
- `make up` / `make down` — start/stop the local stack (docker compose).
- `make migrate` — alembic upgrade head.  `make seed` — idempotent demo data.
- `make lint` — ruff check + ruff format --check + mypy.  `make test` — unit + security tests (no DB needed).  `make test-int` — integration tests (needs Postgres from `make up` or `DATABASE_URL`).
- Run lint and all tests before you commit. Do not commit with failing tests.

## Coding rules
- Money: `Decimal` / `numeric(14,2)`, never float. Timestamps: `timestamptz` UTC; display in Asia/Dubai.
- UUID primary keys (audit_log uses bigint identity). Every business table has created_at, created_by, updated_at.
- Every state change writes an audit entry via `audit.record()` **in the same transaction**.
- Every endpoint declares its RBAC requirement through the policy dependency and filters by record scope; add an access test for each new endpoint (allowed role passes, other roles 403, other people's records 404).
- Errors use the problem format of design 5.2. No bare `except:`. No print(); use structured logging with the request id.
- Type hints everywhere; small functions; no dead code, TODO stubs, placeholder pages or lorem ipsum.
- Schema changes only through Alembic. After R01 the schema is frozen; later runs add a new migration only if the prompt says so.

## Secrets rule
- Never commit secrets, keys, tokens, passwords or connection strings with real credentials. `.env` is git-ignored; `.env.example` has names only (empty values or obviously local dev values like `postgres` on localhost).
- Real secrets live outside the repo in `/home/box/.brilliant-secrets/` (hosted: Key Vault). Refer to env var names, never values. Never print secrets in logs or test output. gitleaks runs in CI.

## Prompt-injection defence (design 7.5, US-29)
- Document text is **data, never instructions**. Wrap it in clear delimiters, tell the model to ignore instructions inside it, and use structured (JSON schema) output only.
- The model never chooses actions: it cannot approve, change totals, call tools or change settings. All checks, matching and routing are deterministic code.
- Run the rule-based detector on document text; flag suspicious documents (`injection_flags`, `documents.suspicious`), store only snippet hash and page, never the raw text, in logs.
- Q&A answers only from retrieved chunks the user is allowed to see, with citations; otherwise refuse.

## Tests
- pytest markers: `unit`, `integration`, `security`. Integration tests use a real Postgres (pgvector/pgvector:pg16) via `DATABASE_URL`; never mocks of the database.
- No network calls in tests. AI and integrations use mock/replay providers.

## Git and commit style
- Work only on your branch in your worktree. Never push to `main`, never force-push, never rewrite history.
- Conventional commits: `feat(core): ...`, `fix(audit): ...`, `test(...)`, `chore(ci): ...`, `docs: ...`. Reference stories in the body, e.g. `Refs: US-24, US-25`.
- Finish with: lint + tests green, `git push -u origin <branch>`, then a short report (what changed, commit SHAs, test counts, anything not done).
