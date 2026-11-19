# Procurement Document Assistant

Technical assessment build for Brilliant Investment & Development (Senior AI & Agentic System Developer).

An AI-assisted procurement workflow for a fictional UAE company: document upload and AI extraction with human review, quote comparison with an explained recommendation, three-way match (PO, delivery note, invoice), Q&A with citations, role-based approvals and an append-only audit trail with prompt-injection defence.

- Requirements: [docs/01-requirements-spec.md](docs/01-requirements-spec.md)
- Design: [docs/02-design.md](docs/02-design.md)
- Sprint plan: [docs/03-sprint-plan.md](docs/03-sprint-plan.md)

Stack: FastAPI, Next.js, Postgres 16 + pgvector, Azure OpenAI, Azure Document Intelligence, Docker, GitHub Actions, Azure Container Apps, Key Vault, Application Insights.

Status: Phase 4 (Build) in progress. All data in this repository is synthetic.

## Run locally

### Prerequisites
- Python 3.12+ and `uv`
- Docker and Docker Compose

### Quick start
1. Generate local environment secrets (writes random `JWT_SECRET`, `DEMO_USER_PASSWORD`, and database passwords to `.env`):
   ```bash
   make env
   ```
2. Start the local stack (Postgres with pgvector, Azurite, FastAPI backend, background worker):
   ```bash
   make up
   ```
   The `api` container automatically applies Alembic migrations on startup.

3. Verify health and database readiness:
   ```bash
   curl -fsS localhost:8000/readyz
   ```

4. Seed demo data (departments and role accounts, idempotent):
   ```bash
   make seed
   ```

5. Log in with a demo account and inspect the authenticated user:
   ```bash
   DEMO_PASSWORD=$(grep "^DEMO_USER_PASSWORD=" .env | cut -d= -f2-)
   TOKEN=$(curl -fsS -X POST http://localhost:8000/api/v1/auth/login \
     -H "Content-Type: application/json" \
     -d "{\"email\":\"buyer1@demo-holdings.example\",\"password\":\"$DEMO_PASSWORD\"}" | \
     python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")

   curl -fsS http://localhost:8000/api/v1/me -H "Authorization: Bearer $TOKEN"
   ```

### Development & Testing
- Linting and typing: `make lint`
- Formatting: `make fmt`
- Unit and security tests: `make test`
- Integration tests (requires running Postgres): `make test-int`
- Stop containers and clean volumes: `docker compose down -v`
