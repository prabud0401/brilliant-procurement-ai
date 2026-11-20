# Infrastructure for Brilliant Procurement AI (PDA)

This directory contains Bicep infrastructure-as-code templates and deployment configuration for hosting the Procurement Document Assistant (PDA) on Microsoft Azure in **UAE North** (`uaenorth`).

> **Demo-only exception: PostgreSQL region.** For this demo the database runs in **North Europe** (`postgresLocation=northeurope`), while everything else stays in UAE North. The demo subscription is not offered Burstable PostgreSQL Flexible Server SKUs in UAE North (`SkuNotAvailable` for B1ms and B2s), and General Purpose would break the demo budget. All data in the demo is synthetic (fake vendors and documents), so data residency does not apply. A real Brilliant deployment would keep PostgreSQL in UAE North (leave `postgresLocation` at its default) on a subscription with that SKU, or use General Purpose.

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
- **`infra/ai.bicep` (Resource-group scope: `rg-brilliant-demo`, Gate G1)**:
  - Azure OpenAI Account (`S0`) in UAE North.
  - Chat deployment: `gpt-5-mini` (version `2025-08-07`, GlobalStandard).
  - Embedding deployment: `text-embedding-3-small` (version `1`, GlobalStandard, 10k TPM).
  - Azure Document Intelligence (`FormRecognizer`, SKU `F0`).
  - Outputs endpoint URLs only, never API keys.
  - Role assignments granting the user-assigned managed identity `Cognitive Services User` (`a97b65f3-24c7-4388-baec-2e87135dc908`).
- **`infra/main.bicep` (Resource-group scope: `rg-brilliant-demo-<env>`, Gate G2)**:
  - Connects and provisions all modules for environment `<env>` (default `prod`).
  - Implements the naming convention `<type>-pda-<env>-uaen` per Design 9.2.
  - Applies mandatory tags: `project=brilliant-demo`, `env=<env>`, `expires=2026-11-29`.
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
  - Administrator login parameter defaulting to `pdaadmin`.
  - Configuration `azure.extensions` allow-listing `VECTOR,PGCRYPTO,UUID-OSSP`.
  - Firewall rule `AllowAllAzureServicesAndResourcesWithinAzureIps` (`0.0.0.0` - `0.0.0.0`) permitting Azure services to connect.
- **`infra/modules/containerapps.bicep`**:
  - Azure Container Apps Environment (`cae-pda-<env>-uaen`, Consumption workload profile) connected to Log Analytics.
  - `ca-web-pda-<env>-uaen`: Web front-end app (external ingress on port 3000, min 0, max 1 replica, probes on `/healthz` and `/readyz`, uses `API_BASE_URL`).
  - `ca-api-pda-<env>-uaen`: API backend app (internal ingress on port 8000, min 0, max 1 replica, probes on `/healthz` and `/readyz`).
  - `ca-worker-pda-<env>-uaen`: Asynchronous document processing worker (no ingress, min 1, max 1 replica, runs `python -m app.worker_main`).
  - All apps mount secrets from Key Vault via the User-Assigned Managed Identity.
  - `migrate` Job: Manual trigger Container Apps job that executes `set -e && alembic upgrade head && python -m app.core.bootstrap && python -m seed.load`.

---

## 2. Gate Order and Process

Infrastructure rollout occurs strictly in two progressive gates:

```
[Gate G1]
  ├── 1. Deploy infra/budget.bicep (subscription scope)
  │      └── USD 20 budget with actual alerts at 50% ($10) and 100% ($20)
  └── 2. Deploy infra/ai.bicep (resource group: rg-brilliant-demo)
         ├── Azure OpenAI (gpt-5-mini & text-embedding-3-small)
         └── Document Intelligence (F0)
         
[Gate G2]
  └── Deploy infra/main.bicep (resource group: rg-brilliant-demo-prod)
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
| **G1, Sat 21 Nov 14:00** | Budget with alerts (first); Azure OpenAI (`gpt-5-mini` and `text-embedding-3-small` deployments); Document Intelligence F0 |
| **G2, Sun 22 Nov 10:00** | Resource group for production; Container Apps environment and three apps; Postgres Flexible Server B1ms; storage account; Key Vault; Application Insights and Log Analytics; managed identity; registry (GHCR, or ACR Basic). **If email intake ships:** Logic App (Consumption) and its Outlook.com API connection |

### Detailed Resource Matrix

| Resource Type | Gate | Target Resource Name | Scope / Group | SKU / Tier |
|---|---|---|---|---|
| Consumption Budget | G1 | `budget-pda-monthly` | Subscription | USD 20/mo |
| Resource Group | G1 | `rg-brilliant-demo` | Subscription | Resource Group |
| Azure OpenAI | G1 | `oai-pda-ai-uaen` | `rg-brilliant-demo` | S0 (GlobalStandard) |
| Document Intelligence | G1 | `di-pda-ai-uaen` | `rg-brilliant-demo` | F0 |
| Resource Group | G2 | `rg-brilliant-demo-prod` | Subscription | Resource Group |
| Managed Identity | G2 | `id-pda-prod-uaen` | `rg-brilliant-demo-prod` | User-Assigned |
| Log Analytics Workspace | G2 | `log-pda-prod-uaen` | `rg-brilliant-demo-prod` | PerGB2018 |
| Application Insights | G2 | `appi-pda-prod-uaen` | `rg-brilliant-demo-prod` | Workspace-based |
| Key Vault | G2 | `kv-pda-prod-uaen` | `rg-brilliant-demo-prod` | Standard (RBAC) |
| Storage Account | G2 | `stpdaproduaen` | `rg-brilliant-demo-prod` | Standard_LRS |
| PostgreSQL Flexible Server | G2 | `psql-pda-prod-uaen` | `rg-brilliant-demo-prod` | Standard_B1ms |
| PostgreSQL Database | G2 | `pda` | `psql-pda-prod-uaen` | UTF-8 |
| Container Apps Environment | G2 | `cae-pda-prod-uaen` | `rg-brilliant-demo-prod` | Consumption |
| Container App (Web) | G2 | `ca-web-pda-prod-uaen` | `rg-brilliant-demo-prod` | External Ingress, 0-1 replicas |
| Container App (API) | G2 | `ca-api-pda-prod-uaen` | `rg-brilliant-demo-prod` | Internal Ingress, 0-1 replicas |
| Container App (Worker) | G2 | `ca-worker-pda-prod-uaen`| `rg-brilliant-demo-prod` | No Ingress, 0-1 replicas |
| Container Apps Job | G2 | `migrate` | `rg-brilliant-demo-prod` | Manual trigger |

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
1. Deletes the primary environment resource group (`rg-brilliant-demo-prod`).
2. Deletes the AI resource group (`rg-brilliant-demo`).
3. Purges the soft-deleted Key Vault (`kv-pda-prod-uaen`) from the subscription so no name collisions or lingering state remain.
4. Purges soft-deleted Cognitive Services accounts.
5. Queries Azure for any remaining resources tagged `project=brilliant-demo` and reports clean status.

---

## 5. Security & Secret Management

- **Zero Hardcoded Secrets**: All passwords and keys are passed via `@secure()` parameters without default values.
- **Role-Based Access Control (RBAC)**: Key Vault uses Azure RBAC authorization rather than access policies. The user-assigned managed identity is granted `Key Vault Secrets User`.
- **Entra Authentication for Storage**: Storage shared keys are disabled (`allowSharedKeyAccess: false`). Managed identity has `Storage Blob Data Contributor`.
- **Cognitive Services**: No API keys are returned or stored. The managed identity is granted `Cognitive Services User`.
- **CI/CD via OIDC**: GitHub Actions authenticates to Azure using OpenID Connect (`azure/login` with `client-id`, `tenant-id`, and `subscription-id`), requiring no long-lived Azure credentials in GitHub.
- **Probe Endpoints**: Liveness and readiness probes query `/healthz` and `/readyz` to verify healthy container operation.

---

## 6. Manual Setup & Prerequisite Configuration

Before triggering deployment via GitHub Actions (`deploy.yml`) or running the deployment scripts, the following one-time manual steps must be performed:

### 1. Microsoft Entra ID OIDC App Registration & Federated Credential
1. In Microsoft Entra ID (Azure Portal or CLI), register an application named `app-pda-github-deploy`.
2. Under **Certificates & secrets** > **Federated credentials**, add a credential:
   - **Federated credential scenario**: GitHub Actions deploying Azure resources.
   - **Organization**: Your GitHub organization or username (`prabud0401`).
   - **Repository**: `brilliant-procurement-ai`.
   - **Entity type**: `Environment`.
   - **Environment name**: `prod`.
3. In Azure Subscriptions > Access Control (IAM), grant this App Registration the `Contributor` and `User Access Administrator` (or `Role Based Access Control Administrator`) role on the subscription or resource group.

### 2. GitHub Environment Secrets List
In the GitHub repository, configure an Environment named `prod` with the following secrets:

| Secret Name | Description | Example / Format |
|---|---|---|
| `AZURE_CLIENT_ID` | Application (Client) ID of the Entra ID app registration | UUID |
| `AZURE_TENANT_ID` | Directory (Tenant) ID of Microsoft Entra ID | UUID |
| `AZURE_SUBSCRIPTION_ID` | Azure Subscription ID | UUID |
| `JWT_SECRET` | Secret key for HS256 JWT tokens (minimum 32 characters) | Base64 / 32+ char string |
| `POSTGRES_ADMIN_PASSWORD` | Administrator password for PostgreSQL server (`pdaadmin`) | Strong alphanumeric + symbol |
| `APP_DB_PASSWORD` | Application user password (`app_user`) | Strong alphanumeric + symbol |
| `DEMO_USER_PASSWORD` | Password for seeded demo user accounts | Strong alphanumeric + symbol |
| `CONTAINER_REGISTRY_USERNAME` | *(Optional)* Private container registry username (leave blank for public GHCR) | String |
| `CONTAINER_REGISTRY_PASSWORD` | *(Optional)* Private container registry password (leave blank for public GHCR) | String |
| `INTAKE_KEY` | *(Optional)* Plain API key for email intake Logic App (required when `ENABLE_EMAIL_INTAKE` is true) | Alphanumeric string |
| `ENABLE_EMAIL_INTAKE` | *(Optional)* Variable to enable email intake (`true`/`false`, default `false`) | Boolean string |

### 3. Making GitHub Container Registry (GHCR) Packages Public
By default, GitHub Packages for private repositories are published with private visibility. Because `GITHUB_TOKEN` expires when the workflow run finishes, Container Apps cannot use it for future container pulls (e.g. scaling up from zero or node restarts).

1. After the initial build pushes images to GHCR:
   - `ghcr.io/<owner>/backend`
   - `ghcr.io/<owner>/web`
2. Go to repository page > **Packages** tab (or profile Packages).
3. Select the package (`backend` / `web`) > **Package settings**.
4. Scroll to **Danger Zone** > **Change package visibility**.
5. Select **Public** and confirm.
6. With public packages, Container Apps pulls images directly without requiring registry credentials or tokens.

---

## 7. Email Intake via Azure Logic Apps (R13 Stretch)

When enabled (`enableEmailIntake=true`), the infrastructure provisions an automated email intake pipeline connecting an Outlook.com demo mailbox to the Procurement Document Assistant API.

### Components Deployed
- **Logic App (Consumption)**: `logic-pda-${env}-uaen`
- **Outlook.com API Connection**: `outlook-pda-${env}-uaen` (`Microsoft.Web/connections`, managed API `outlook`)

### Workflow Behavior
1. **Trigger**: "When a new email arrives (V2)" polls the mailbox every 5 minutes with `hasAttachments=true` and `includeAttachments=true`.
2. **Filtering**: For each attachment, checks that the MIME type or file extension is PDF, PNG, or JPEG, and file size is $\le$ 4 MB (or configured limit). Non-matching files (e.g. `.exe`, `.zip`, oversized files) are skipped.
3. **API Delivery**: Approved attachments are sent via HTTP POST to `${apiBaseUrl}/api/v1/intake/email` with header `X-Intake-Key: <intakeKey>`, sender, subject, received time, and message ID. Inputs and outputs on the HTTP action are secured (`secureData`).

### Key Generation and Secret Routing
Email intake authentication requires a shared API key between the Logic App and the API backend:
1. **Key and Hash Generation**:
   Run the intake keygen tool:
   ```bash
   python -m app.intake.keygen
   ```
   This generates a secure random plain key and its Argon2id hash.
2. **Where Each Value Goes**:
   - **Plain key (`intakeKey`)**: Provided to the Logic App secure parameter or GitHub secret `INTAKE_KEY`. The plain key must never be stored in Key Vault for the api or appear in any file, template environment, or response.
   - **Hash (`intake-key-hash`)**: Stored in Key Vault secret `intake-key-hash` (e.g. via `az keyvault secret set --vault-name kv-pda-<env>-uaen --name intake-key-hash --value "<hash>"` or passed via `intakeKeyHash`). The api Container App mounts this via Key Vault reference as `INTAKE_KEY_HASH`.
3. **Sender Allowlist**:
   - `INTAKE_SENDER_ALLOWLIST`: Configured as a plain environment variable on the api Container App from parameter `intakeSenderAllowlist` (default empty, which allows all senders).

### One-Time Manual Sign-In Step
Because Azure Logic Apps API connections require interactive OAuth consent to connect to an Outlook.com account:
1. Deploy with `enableEmailIntake=true` and provide `intakeKey`.
2. Open the Azure Portal and navigate to `rg-brilliant-demo-<env>`.
3. Select the API Connection resource: `outlook-pda-<env}-uaen`.
4. In the left navigation, click **Edit API connection**.
5. Click **Authorize** and sign in with the demo-only Outlook.com mailbox credentials.
6. Click **Save**. The Logic App trigger is now active and polling.

### Teardown Note
The Logic App and Outlook API connection are deployed within the environment resource group (`rg-brilliant-demo-<env>`). Running `scripts/teardown.sh <env>` deletes this resource group in full, automatically destroying the Logic App, the API connection, and revoking associated session tokens. Key Vault secrets containing the intake key and hash are purged as part of standard teardown.


