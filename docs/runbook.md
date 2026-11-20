# Operations & Deployment Runbook

This runbook provides step-by-step operational procedures for running, deploying, verifying, rotating secrets, rolling back, and tearing down the **Procurement Document Assistant (PDA)**.

---

## 1. Local Operations & Environment Reset

### 1.1 First-Time Local Startup
From the repository root:

```bash
# 1. Generate local environment configuration and secure secrets in .env
make env

# 2. Build and start local containers (PostgreSQL, Azurite, API, Worker, Web)
make up

# 3. Seed demo master data, roles, and initial users (idempotent)
make seed

# 4. Generate synthetic document fixtures and verify ground-truth integrity
make datagen
```

The application is accessible at:
- **Web Interface:** [http://localhost:3000](http://localhost:3000)
- **FastAPI Documentation:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Check:** `curl -fsS http://localhost:8000/healthz`

### 1.2 Stopping the Local Stack
```bash
# Stop containers without removing persistent database volumes
make down
```

### 1.3 Full Reset (Clean Slate)
To wipe all local state, reset database tables, and purge blob storage:
```bash
# Stop containers and remove named volumes (pgdata)
docker compose down -v

# Regenerate fresh secrets and restart
make env
make up
make seed
make datagen
```

---

## 2. Production Deployment (Azure UAE North)

> Demo note: PostgreSQL is deployed to North Europe with `POSTGRES_LOCATION=northeurope ./scripts/deploy.sh prod g2` because the demo subscription has no Burstable Postgres SKU in UAE North. Data is synthetic. See `infra/README.md`.

> [!NOTE]
> Azure deployment commands require an active Azure subscription with permissions to create resource groups, role assignments, and Azure Container Apps.

### 2.1 One-Time Manual Prerequisites
Before triggering continuous deployment via GitHub Actions, perform these one-time setup steps per `infra/README.md`:

1. **Microsoft Entra ID OIDC App Registration**:
   - Register an Entra ID application named `app-pda-github-deploy`.
   - Under **Certificates & secrets** > **Federated credentials**, add a credential:
     - **Scenario:** GitHub Actions deploying Azure resources
     - **Organization:** `prabud0401`
     - **Repository:** `brilliant-procurement-ai`
     - **Entity Type:** `Environment`
     - **Environment Name:** `prod`
   - Grant the application `Contributor` and `User Access Administrator` (or `Role Based Access Control Administrator`) on the target Azure subscription.

2. **Configure GitHub Environment Secrets**:
   In the repository settings under **Environments** > `prod`, configure the following secrets (names only; never commit real values):

   | Secret Name | Description |
   |---|---|
   | `AZURE_CLIENT_ID` | Application (Client) ID of the Entra ID app registration |
   | `AZURE_TENANT_ID` | Directory (Tenant) ID of Microsoft Entra ID |
   | `AZURE_SUBSCRIPTION_ID` | Target Azure Subscription ID |
   | `JWT_SECRET` | Secret key for HS256 tokens (min 32 random characters) |
   | `POSTGRES_ADMIN_PASSWORD` | Administrator password for PostgreSQL server (`pdaadmin`) |
   | `APP_DB_PASSWORD` | Dedicated application user database password (`app_user`) |
   | `DEMO_USER_PASSWORD` | Shared password for seeded demo role accounts |
   | `INTAKE_KEY` | *(Optional)* Shared key for Logic App email intake |

3. **Deploy Subscription Cost Budget (Gate G1)**:
   Deploy the monthly spending limit before any hosting resources are created:
   ```bash
   az deployment sub create \
     --location uaenorth \
     --template-file infra/budget.bicep \
     --parameters alertEmail="admin@demo-holdings.example"
   ```

4. **Deploy AI Services (Gate G1)**:
   ```bash
   az group create --name rg-pda-ai-uaen --location uaenorth --tags project=brilliant-pda
   az deployment group create \
     --resource-group rg-pda-ai-uaen \
     --template-file infra/ai.bicep
   ```

### 2.2 Triggering Deployment via GitHub Actions
Production deployments are automated via `.github/workflows/deploy.yml`:
1. Push a release tag starting with `v` (e.g. `git tag v0.1.0-demo && git push origin v0.1.0-demo`).
2. The workflow builds container images, publishes to GitHub Container Registry (GHCR), authenticates via OIDC, runs Bicep `what-if` validation, provisions `rg-pda-prod-uaen`, executes the migration Container App Job, and runs the smoke test suite against the live endpoint.

### 2.3 Manual Deployment Script
To preview and deploy from an operator terminal:
```bash
# Preview what-if and deploy with interactive confirmation
scripts/deploy.sh prod

# Non-interactive CI deployment
scripts/deploy.sh prod all --yes
```

---

## 3. Deployment Verification & Health Checks

### 3.1 Probes and Readiness
Verify that all services are operational:
```bash
# Container liveness check (HTTP 200)
curl -fsS https://<app-domain>/healthz

# Database and readiness check (HTTP 200)
curl -fsS https://<app-domain>/readyz
```

### 3.2 Automated Smoke Test Suite
Run the automated smoke test script against the target endpoint:
```bash
# Runs health checks, sign-in validation, session cookie checks, and /me verification
./scripts/smoke.sh https://<app-domain>
```

---

## 4. Rollback Procedures

### 4.1 Application Image Rollback
If a defect is discovered in production, revert Container Apps to the previous image SHA:

```bash
PREV_SHA="<previous-git-sha>"
RG="rg-pda-prod-uaen"

# Update web app revision
az containerapp update \
  --name ca-web-pda-prod-uaen \
  --resource-group "$RG" \
  --image "ghcr.io/prabud0401/web:${PREV_SHA}"

# Update API app revision
az containerapp update \
  --name ca-api-pda-prod-uaen \
  --resource-group "$RG" \
  --image "ghcr.io/prabud0401/backend:${PREV_SHA}"

# Update Worker app revision
az containerapp update \
  --name ca-worker-pda-prod-uaen \
  --resource-group "$RG" \
  --image "ghcr.io/prabud0401/backend:${PREV_SHA}"
```

### 4.2 Database Migration Rollback Note
- The database schema is backward-compatible.
- If a schema downgrade is strictly required:
  ```bash
  cd services/backend
  DATABASE_URL="$DATABASE_URL_MIGRATOR" uv run alembic downgrade -1
  ```
  > [!WARNING]
  > Downgrading migrations drops newly created columns or tables, potentially resulting in data loss for records created during the deployment window.

---

## 5. Secret Rotation Procedures

To rotate credentials without downtime:

1. **Update Secrets in Azure Key Vault**:
   ```bash
   VAULT="kv-pda-prod-uaen"

   # Rotate JWT Secret
   NEW_JWT=$(openssl rand -base64 32)
   az keyvault secret set --vault-name "$VAULT" --name "jwt-secret" --value "$NEW_JWT"

   # Rotate Demo Password
   NEW_DEMO_PWD=$(openssl rand -base64 16)
   az keyvault secret set --vault-name "$VAULT" --name "demo-user-password" --value "$NEW_DEMO_PWD"
   ```

2. **Restart Container Revisions**:
   Restart container revisions to pull the updated secret values from Key Vault:
   ```bash
   az containerapp revision restart --name ca-api-pda-prod-uaen --resource-group rg-pda-prod-uaen
   az containerapp revision restart --name ca-worker-pda-prod-uaen --resource-group rg-pda-prod-uaen
   ```

---

## 6. Switching AI Modes (Replay ↔ Live)

The system supports swapping between offline replay and live Azure AI services via environment variable `AI_PROVIDER`:

1. **Switch to Replay Mode (Zero Cost / Offline)**:
   ```bash
   # In local .env or Container App environment variables:
   AI_PROVIDER=replay
   ```
   Uses pre-recorded Document Intelligence and OpenAI fixtures from `eval/data/replay/`.

2. **Switch to Live Mode (Azure OpenAI & Document Intelligence)**:
   Ensure the following settings are provided:
   ```bash
   AI_PROVIDER=live
   AZURE_OPENAI_ENDPOINT=https://<resource>.openai.azure.com/
   AZURE_OPENAI_DEPLOYMENT=gpt-5-mini
   AZURE_OPENAI_EMBEDDING_DEPLOYMENT=text-embedding-3-small
   AZURE_OPENAI_API_VERSION=2025-04-01-preview
   AZURE_OPENAI_REASONING_EFFORT=low
   AZURE_DOCINTEL_ENDPOINT=https://<resource>.cognitiveservices.azure.com/
   AI_DAILY_BUDGET_AED=7.0
   ```
   In Azure, authentication is handled automatically via User-Assigned Managed Identity (`Cognitive Services User` role). In local environments, `az login` credentials or service principal credentials are used.

   To execute live evaluation and record real fixtures:
   ```bash
   cd services/backend && uv run python -m eval.run --mode live --confirm-live --max-cost-usd 3 --record-replay
   ```

---

## 7. Infrastructure Teardown & Zero-Cost Verification

To dismantle all hosted infrastructure upon conclusion of the demo period:

### 7.1 Executing Teardown
```bash
# Automated one-command teardown script (requires an Azure subscription)
scripts/teardown.sh prod --yes
```

The script performs the following operations:
1. Deletes the application resource group (`rg-pda-prod-uaen`), terminating all Container Apps, Postgres instances, and storage accounts.
2. Deletes the AI resource group (`rg-pda-ai-uaen`).
3. Purges soft-deleted Key Vaults (`kv-pda-prod-uaen`) to prevent name collisions.
4. Purges soft-deleted Cognitive Services accounts.
5. Queries for any lingering resources tagged `project=brilliant-pda`.

### 7.2 Post-Teardown Zero-Cost Verification
72 hours following teardown, log into the Azure Portal:
- Navigate to **Cost Management + Billing** > **Cost Analysis**.
- Filter by tag `project=brilliant-pda`.
- Confirm that daily amortized and actual charges drop to $0.00.

---

## 8. Troubleshooting Guide (Top 8 Operational Issues)

| # | Symptom | Root Cause | Resolution |
|---|---|---|---|
| **1** | `bind: address already in use` during `make up` | A local process is holding port 5432, 8000, 3000, or 10000. | Check conflicting ports: `lsof -i :<port>`. Either terminate the conflicting process or override ports in `.env` (e.g. `DB_PORT=55452 API_PORT=8022 WEB_PORT=3022`). |
| **2** | `api` container unhealthy or continuously restarting | Database container `db` is still initializing or migrations failed. | Inspect database logs: `docker compose logs db`. Verify `DATABASE_URL_MIGRATOR` in `.env` has valid credentials. |
| **3** | `alembic: command not found` or migration mismatch | Alembic run outside the virtual environment. | Always execute migrations via `uv`: `cd services/backend && uv run alembic upgrade head`. |
| **4** | Blob upload fails (`ConnectionRefusedError` to Azurite) | Azurite container is not running or blob port mapping is mismatched. | Ensure Azurite is active: `docker compose up -d azurite`. Verify `.env` has `BLOB_CONNECTION_STRING=UseDevelopmentStorage=true`. |
| **5** | 401 Unauthorized / Token Missing on UI navigation | Cookie rejected due to domain/secure mismatch or expired JWT token. | Verify Next.js BFF is forwarding cookie headers. In non-HTTPS local dev, ensure `NODE_ENV` permits unencrypted session cookies on `localhost`. |
| **6** | Live AI calls return 401 or 403 Forbidden | Managed Identity lacks `Cognitive Services User` role on OpenAI/DocIntel. | Verify Azure role assignments in `rg-pda-ai-uaen`: `az role assignment list --assignee <identity-principal-id>`. |
| **7** | Playwright E2E tests fail immediately with connection refused | Playwright defaulting to an incorrect host port. | Specify target base URL explicitly: `WEB_BASE_URL=http://localhost:3000 npx playwright test`. |
| **8** | Document extraction stuck in `pending` status | Background worker container is not running or crashed. | Check worker logs: `docker compose logs worker`. Restart worker: `docker compose restart worker`. |
