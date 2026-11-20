# Infrastructure for Brilliant Procurement AI (PDA)

This directory contains Bicep infrastructure-as-code templates and deployment configuration for hosting the Procurement Document Assistant (PDA) on Microsoft Azure in **UAE North** (`uaenorth`).

---

## 1. File Structure and What Each File Creates

```
infra/
├── main.bicep                    # Main orchestrator (resource-group scope, Gate G2)
├── ai.bicep                      # Azure OpenAI & Document Intelligence (Gate G1)
├── budget.bicep                  # Subscription-scope cost budget and alert thresholds (Gate G1)
├── modules/
│   ├── identity.bicep            # User-assigned managed identity
│   ├── monitoring.bicep          # Log Analytics workspace and workspace-based Application Insights
│   ├── database.bicep            # Azure Database for PostgreSQL Flexible Server (Burstable B1ms, pgvector, pda database)
│   ├── keyvault.bicep            # Azure Key Vault (RBAC mode, soft delete ON, purge protection OFF, secrets)
│   ├── storage.bicep             # Azure Storage account (TLS 1.2, private documents container, Entra MI auth)
│   └── containerapps.bicep       # Container Apps environment, 3 apps (web, api, worker), and migrate job
scripts/
├── deploy.sh                     # Interactive/automated deployment helper (what-if preview then create)
└── teardown.sh                   # One-command teardown script (deletes RGs, purges KV and AI, checks tags)
.github/workflows/
├── deploy.yml                    # Automated deploy and teardown workflow (v* tags, OIDC, GHCR, smoke tests)
└── ci.yml                        # CI pipeline including Bicep build/lint and ShellCheck
```

### Component Details

- **`infra/budget.bicep` (Subscription scope, Gate G1)**:
  - Deploys a monthly subscription budget of USD 20 with notifications at 50% actual (USD 10) and 100% actual (USD 20) sent to the configured alert email.
- **`infra/ai.bicep` (Resource-group scope: `rg-pda-ai-uaen`, Gate G1)**:
  - Azure OpenAI Account (`S0`) in UAE North.
  - Chat deployment: `gpt-4o-mini` (version `2024-07-18`, GlobalStandard, 10k TPM).
  - Embedding deployment: `text-embedding-3-small` (version `1`, GlobalStandard, 10k TPM).
  - Azure Document Intelligence (`FormRecognizer`, SKU `F0`).
  - Outputs endpoint URLs only, never API keys.
  - Role assignments granting the user-assigned managed identity `Cognitive Services User` (`a97b65f3-24c7-4388-baec-2e87135dc908`).
- **`infra/main.bicep` (Resource-group scope: `rg-pda-<env>-uaen`, Gate G2)**:
  - Connects and provisions all modules for environment `<env>` (default `prod`).
  - Implements the naming convention `<type>-pda-<env>-uaen` per Design 9.2.
  - Applies mandatory tags: `project=brilliant-pda`, `env=<env>`, `owner=prabudeva`, `expires=2026-11-29`.
- **`infra/modules/identity.bicep`**:
  - User-assigned managed identity (`id-pda-<env>-uaen`).
- **`infra/modules/monitoring.bicep`**:
  - Log Analytics workspace (`log-pda-<env>-uaen`, PerGB2018, 30 days retention).
  - Workspace-based Application Insights (`appi-pda-<env>-uaen`).
- **`infra/modules/keyvault.bicep`**:
  - Azure Key Vault (`kv-pda-<env>-uaen`).
  - Configured with Azure RBAC authorization enabled, soft delete enabled, and purge protection disabled for clean teardown.
  - Managed identity is granted `Key Vault Secrets User` (`4633458b-17de-408a-b874-0445c86b69e6`).
  - Stores `@secure()` secrets without default values: `jwt-secret`, `postgres-admin-password`, `app-db-password`, `demo-user-password`, `database-url`, `database-url-migrator`, and optional `container-registry-password`.
- **`infra/modules/storage.bicep`**:
  - Storage account (`stpda<env>uaen`, Standard_LRS, Hot tier).
  - Enforces `minimumTlsVersion: TLS1_2`, `supportsHttpsTrafficOnly: true`, `allowBlobPublicAccess: false`, and `allowSharedKeyAccess: false` (Entra ID / Managed Identity only).
  - Private blob container `documents`.
  - Managed identity is granted `Storage Blob Data Contributor` (`ba92f5b4-2d11-453d-a403-e96b0029c9fe`).
- **`infra/modules/database.bicep`**:
  - Azure Database for PostgreSQL Flexible Server (`psql-pda-<env>-uaen`, Burstable `Standard_B1ms`, PostgreSQL 16, 32 GB storage, 7-day backup retention, High Availability disabled).
  - Database named `pda`.
  - Configuration `azure.extensions` allow-listing `VECTOR,PGCRYPTO`.
  - Firewall rule `AllowAllAzureServicesAndResourcesWithinAzureIps` (`0.0.0.0` - `0.0.0.0`) permitting Azure services to connect.
- **`infra/modules/containerapps.bicep`**:
  - Azure Container Apps Environment (`cae-pda-<env>-uaen`, Consumption workload profile) connected to Log Analytics.
  - `ca-web-pda-<env>-uaen`: Web front-end app (external ingress on port 3000, min 0, max 1 replica, probes on `/healthz` and `/readyz`).
  - `ca-api-pda-<env>-uaen`: API backend app (internal ingress on port 8000, min 0, max 1 replica, probes on `/healthz` and `/readyz`).
  - `ca-worker-pda-<env>-uaen`: Asynchronous document processing worker (no ingress, min 0, max 1 replica, runs `python -m app.worker_main`).
  - All apps mount secrets from Key Vault via the User-Assigned Managed Identity.
  - `migrate` Job: Manual trigger Container Apps job that executes `alembic upgrade head && python -m app.core.bootstrap && python -m seed.load`.

---

## 2. Gate Order and Process

Infrastructure rollout occurs strictly in two progressive gates:

```
[Gate G1]
  ├── 1. Deploy infra/budget.bicep (subscription scope)
  │      └── USD 20 budget with actual alerts at 50% ($10) and 100% ($20)
  └── 2. Deploy infra/ai.bicep (resource group: rg-pda-ai-uaen)
         ├── Azure OpenAI (gpt-4o-mini & text-embedding-3-small)
         └── Document Intelligence (F0)
         
[Gate G2]
  └── Deploy infra/main.bicep (resource group: rg-pda-prod-uaen)
      ├── Managed Identity & RBAC role assignments
      ├── Log Analytics & Application Insights
      ├── Key Vault with secure parameters
      ├── Storage Account & documents container
      ├── PostgreSQL Flexible Server (B1ms, pgvector, pda database)
      ├── Container Apps Environment
      ├── Container Apps (web, api, worker)
      └── Container Apps Job (migrate)
```

---

## 3. Expected Resource List per Gate

This list exactly matches **Sprint Plan 9.1**:

| Gate | Resources created after approval |
|---|---|
| **G1, Sat 21 Nov 14:00** | Budget with alerts (first); Azure OpenAI (`gpt-4o-mini` and `text-embedding-3-small` deployments); Document Intelligence F0 |
| **G2, Sun 22 Nov 10:00** | Resource group for production; Container Apps environment and three apps; Postgres Flexible Server B1ms; storage account; Key Vault; Application Insights and Log Analytics; managed identity; registry (GHCR, or ACR Basic). **If email intake ships:** Logic App (Consumption) and its Outlook.com API connection |

### Detailed Resource Matrix

| Resource Type | Gate | Target Resource Name | Scope / Group | SKU / Tier |
|---|---|---|---|---|
| Consumption Budget | G1 | `budget-pda-monthly` | Subscription | USD 20/mo |
| Resource Group | G1 | `rg-pda-ai-uaen` | Subscription | Resource Group |
| Azure OpenAI | G1 | `oai-pda-ai-uaen` | `rg-pda-ai-uaen` | S0 (GlobalStandard) |
| Document Intelligence | G1 | `di-pda-ai-uaen` | `rg-pda-ai-uaen` | F0 |
| Resource Group | G2 | `rg-pda-prod-uaen` | Subscription | Resource Group |
| Managed Identity | G2 | `id-pda-prod-uaen` | `rg-pda-prod-uaen` | User-Assigned |
| Log Analytics Workspace | G2 | `log-pda-prod-uaen` | `rg-pda-prod-uaen` | PerGB2018 |
| Application Insights | G2 | `appi-pda-prod-uaen` | `rg-pda-prod-uaen` | Workspace-based |
| Key Vault | G2 | `kv-pda-prod-uaen` | `rg-pda-prod-uaen` | Standard (RBAC) |
| Storage Account | G2 | `stpdaproduaen` | `rg-pda-prod-uaen` | Standard_LRS |
| PostgreSQL Flexible Server | G2 | `psql-pda-prod-uaen` | `rg-pda-prod-uaen` | Standard_B1ms |
| PostgreSQL Database | G2 | `pda` | `psql-pda-prod-uaen` | UTF-8 |
| Container Apps Environment | G2 | `cae-pda-prod-uaen` | `rg-pda-prod-uaen` | Consumption |
| Container App (Web) | G2 | `ca-web-pda-prod-uaen` | `rg-pda-prod-uaen` | External Ingress, 0-1 replicas |
| Container App (API) | G2 | `ca-api-pda-prod-uaen` | `rg-pda-prod-uaen` | Internal Ingress, 0-1 replicas |
| Container App (Worker) | G2 | `ca-worker-pda-prod-uaen`| `rg-pda-prod-uaen` | No Ingress, 0-1 replicas |
| Container Apps Job | G2 | `migrate` | `rg-pda-prod-uaen` | Manual trigger |

---

## 4. One-Command Deploy and Teardown

### Deploying the Infrastructure

To deploy manually (Gate G1 + Gate G2) with interactive confirmation and automatic `what-if` preview:

```bash
scripts/deploy.sh prod
```

Or deploy a specific gate:

```bash
# Gate G1 only (Budget + AI)
scripts/deploy.sh prod g1

# Gate G2 only (Main stack)
scripts/deploy.sh prod g2
```

The script previews all changes with `az deployment ... what-if` before prompting the operator to proceed with `az deployment ... create`.

### Tearing Down the Infrastructure

To delete all hosted resources with a single command:

```bash
# Interactive prompt (requires typing 'DELETE'):
scripts/teardown.sh prod

# Non-interactive / CI teardown:
scripts/teardown.sh prod --yes
```

The teardown script performs the following in sequence:
1. Deletes the primary environment resource group (`rg-pda-prod-uaen`).
2. Deletes the AI resource group (`rg-pda-ai-uaen`).
3. Purges the soft-deleted Key Vault (`kv-pda-prod-uaen`) from the subscription so no name collisions or lingering state remain.
4. Purges soft-deleted Cognitive Services accounts.
5. Queries Azure for any remaining resources tagged `project=brilliant-pda` and reports clean status.

---

## 5. Security & Secret Management

- **Zero Hardcoded Secrets**: All passwords and keys are passed via `@secure()` parameters without default values.
- **Role-Based Access Control (RBAC)**: Key Vault uses Azure RBAC authorization rather than access policies. The user-assigned managed identity is granted `Key Vault Secrets User`.
- **Entra Authentication for Storage**: Storage shared keys are disabled (`allowSharedKeyAccess: false`). Managed identity has `Storage Blob Data Contributor`.
- **Cognitive Services**: No API keys are returned or stored. The managed identity is granted `Cognitive Services User`.
- **CI/CD via OIDC**: GitHub Actions authenticates to Azure using OpenID Connect (`azure/login` with `client-id`, `tenant-id`, and `subscription-id`), requiring no long-lived Azure credentials in GitHub.
- **Probe Endpoints**: Liveness and readiness probes query `/healthz` and `/readyz` to verify healthy container operation.
