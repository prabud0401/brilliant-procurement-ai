# Procurement Document Assistant — System Architecture

This document describes the architectural design, component responsibilities, end-to-end request flows, data model, security controls, observability implementation, and cloud deployment topology for the **Procurement Document Assistant (PDA)**.

---

## 1. System Overview & Component Responsibilities

The system is organized into modular services with strict separation between user-facing presentation, business logic orchestration, deterministic evaluation, and AI capabilities.

```mermaid
flowchart TD
    subgraph Client["Client Tier"]
        Browser["User Browser (Desktop/Mobile)"]
    end

    subgraph Presentation["Presentation & BFF Tier"]
        Web["Next.js App Router (apps/web)<br/>Port 3000 | BFF Proxy & Auth Cookies"]
    end

    subgraph Service["Backend & Core Processing Tier"]
        API["FastAPI Application (services/backend)<br/>Port 8000 | REST API & RBAC Enforcement"]
        Worker["Background Processing Worker<br/>Async Job Queue Poller"]
    end

    subgraph Storage["Persistence & State Tier"]
        DB[("PostgreSQL 16 + pgvector<br/>Port 5432 | Relational + Embeddings")]
        Blob[("Object Storage (Azure Blob / Azurite)<br/>Port 10000 | Container: documents")]
    end

    subgraph AI["AI Module Tier (app/ai)"]
        AI_Factory["AI Provider Factory"]
        DI["Azure Document Intelligence (or Replay/Mock)"]
        OAI["Azure OpenAI Chat (default gpt-5-mini) & Embeddings"]
    end

    subgraph Integrations["Integration Adapters (app/integrations)"]
        Odoo["Odoo ERP Adapter (Mock)"]
        SharePoint["SharePoint Adapter (Mock)"]
        PowerAutomate["Power Automate Adapter (Mock)"]
    end

    subgraph Ingestion["Automated Intake"]
        LogicApp["Azure Logic App (Consumption)<br/>Polls Demo Mailbox every 5m"]
    end

    Browser <-->|HTTPS / Session Cookie| Web
    Web <-->|Internal HTTP / Bearer JWT| API
    LogicApp -->|HTTPS / Service API Key| API
    API -->|Write Job & Metadata| DB
    API -->|Upload / Download| Blob
    Worker <-->|Poll Jobs & State Transitions| DB
    Worker -->|Fetch Document Content| Blob
    Worker -->|Analyze / Embed| AI_Factory
    API -->|Q&A & Comparison| AI_Factory
    AI_Factory --> DI
    AI_Factory --> OAI
    API -.->|Query Master Data & Sync| Integrations
```

### Component Details

1. **Web Front-End / Backend-for-Frontend (`apps/web`)**:
   - Built with Next.js 15 (App Router), TypeScript, and Tailwind CSS.
   - Operates as a Backend-For-Frontend (BFF): handles authentication routes (`/api/auth/*`), proxies API requests, and secures JWT access tokens inside `httpOnly`, `Secure`, `SameSite=Lax` cookies, preventing client-side script access.
   - Provides split-screen PDF document review with bounding-box canvas overlays, side-by-side quote comparison tables, one-screen approval bundles, match exception resolution queues, and conversational Q&A interfaces.

2. **Backend API (`services/backend/app/main.py`)**:
   - Built with Python 3.12, FastAPI, and Pydantic v2.
   - Enforces Role-Based Access Control (RBAC) and departmental row-level scoping via FastAPI dependency injection (`PolicyChecker`).
   - Implements deterministic business algorithms: quote comparison scoring, three-way match tolerance checks, approval routing tiers, and segregation of duties.
   - Generates problem detail JSON responses (`application/problem+json`) per RFC 7807 for consistent error reporting.

3. **Background Worker (`services/backend/app/worker_main.py`)**:
   - Executes asynchronous tasks managed via the database job queue (`jobs` table).
   - Responsible for document OCR extraction, line item parsing, validation rule execution, vector chunking, and embedding generation upon document confirmation. Untyped and email-intake documents are auto-classified after OCR and before extraction.

4. **Database & Vector Store (`db`)**:
   - PostgreSQL 16 equipped with the `pgvector` extension.
   - Stores all transactional procurement entities, audit logs, background jobs, and 1536-dimensional vector embeddings for Q&A document chunks.
   - Schema revisions are managed strictly through typed Alembic migrations.

5. **Blob Storage (`azurite` / Azure Blob Storage)**:
   - Houses raw uploaded PDFs, delivery receipts, and vendor invoices in a private `documents` container.
   - In production, public access is disabled, TLS 1.2 is enforced, and access is restricted to Microsoft Entra managed identity credentials (`allowSharedKeyAccess: false`).

6. **AI Module Interface (`services/backend/app/ai`)**:
   - Central abstraction layer isolating all machine learning interactions.
   - Supports three runtime providers: `mock` (deterministic unit testing), `replay` (high-fidelity offline test fixtures), and `live` (Azure Document Intelligence and Azure OpenAI; chat model is configurable, default `gpt-5-mini`).

7. **Integration Adapters (`services/backend/app/integrations`)**:
   - Pluggable interfaces for Odoo ERP, SharePoint, and Power Automate Teams notifications.
   - Running in `mock` mode with realistic in-memory stores during demo evaluation, ready for live API connectors without modifying core domain logic.

---

## 2. End-to-End Request Flows

### 2.1 Upload → Extraction → Review → Match → Approval Flow

The procurement lifecycle enforces validation, human-in-the-loop review, deterministic scoring, and separation of duties:

```mermaid
sequenceDiagram
    autonumber
    actor Buyer as Buyer
    actor Requester as Requester
    actor Manager as Manager
    participant Web as Next.js BFF
    participant API as FastAPI Backend
    participant Worker as Background Worker
    participant AI as AI Module (DI / LLM)
    participant DB as PostgreSQL 16
    participant Blob as Blob Storage

    %% Document Upload & Extraction
    Buyer->>Web: Upload Quotation PDF
    Web->>API: POST /api/v1/documents/upload
    API->>API: Validate file type, size, SHA-256 duplicate
    API->>Blob: Store raw document binary
    API->>DB: Insert document (status: uploaded) & job
    API-->>Web: Document metadata & tracking ID
    Worker->>DB: Claim pending extraction job
    Worker->>AI: Extract fields, layout, line items & scan injection
    AI-->>Worker: Extracted fields, bounding boxes, flags
    Worker->>Worker: Rule-based arithmetic & validation checks
    Worker->>DB: Save extraction, fields, lines, flags (status: extracted)

    %% Human Review & Confirmation
    Buyer->>Web: Open Review Screen (/documents/:id)
    Web->>API: GET /api/v1/documents/:id/review
    API-->>Web: Fields, bounding boxes, validation flags
    Buyer->>Web: Correct field (e.g. payment terms) & confirm
    Web->>API: POST /api/v1/documents/:id/confirm
    API->>DB: Update document status: confirmed
    API->>DB: audit.record(document.confirmed) in same transaction
    API->>DB: Enqueue chunking & embedding job

    %% Purchase Request & Comparison
    Requester->>Web: Create Purchase Request (PR) & Submit
    Web->>API: POST /api/v1/requests
    API->>DB: Create PR (status: submitted)
    Buyer->>Web: Compare linked quotes (/comparisons/new)
    Web->>API: POST /api/v1/comparisons (generate recommendation)
    API->>API: Deterministic multi-criteria scoring (60/20/10/10)
    API->>AI: Generate explanation from facts JSON
    API->>API: Faithfulness check: verify figures against source facts
    API-->>Web: Recommended vendor, score matrix, verified explanation
    Buyer->>Web: Select vendor (or override with >= 10 char reason) & Create PO
    Web->>API: POST /api/v1/purchase-orders

    %% Approval Flow
    Buyer->>Web: Submit PO for Approval
    Web->>API: POST /api/v1/purchase-orders/:id/submit
    API->>API: Determine approval tier & route to eligible Manager
    API->>DB: Create approval step (status: pending)
    Manager->>Web: Open One-Screen Approval Bundle (/approvals/:id)
    Manager->>Web: Approve Commitment
    Web->>API: POST /api/v1/approvals/:id/decision (decision: approve)
    API->>API: Enforce SoD (Reject if approver == requester or buyer)
    API->>DB: Update PO status: approved, audit.record()

    %% Three-Way Match
    Note over Worker,DB: When Invoice & Delivery Note are uploaded & confirmed:
    Worker->>API: Execute Three-Way Match (PO vs DN vs Invoice)
    API->>API: Check line items, quantities, unit prices against tolerances
    alt Match Clean
        API->>DB: Create Match record (status: matched)
    else Variance Detected (e.g. S3 Qty 12 vs 10)
        API->>DB: Create Match record (status: exception) & exception rows
        Buyer->>Web: View Match Exceptions (/matches)
        Note over Buyer,Web: Over-billed quantity cannot be accepted by Buyer (blocked)
        Buyer->>Web: Escalate exception to Manager with reason
        Web->>API: POST /api/v1/matches/exceptions/:id/resolve (action: escalate)
        Manager->>Web: Decide on escalation (Reject invoice over-billing)
        Web->>API: POST /api/v1/matches/exceptions/:id/resolve (action: reject)
    end
```

---

### 2.2 Q&A Semantic Retrieval Flow

The Q&A assistant answers natural-language queries regarding procurement documents using hybrid search, role-based document scoping, and citation verification:

```mermaid
sequenceDiagram
    autonumber
    actor User as Authenticated User
    participant Web as Next.js BFF
    participant API as FastAPI Backend
    participant DB as PostgreSQL (pgvector + tsvector)
    participant AI as Azure OpenAI (Embeddings + Chat: default gpt-5-mini)

    User->>Web: Submit Query (e.g. "What are Gulf Line payment terms?")
    Web->>API: POST /api/v1/qa/ask
    API->>API: Scan question for prompt injection attempts
    API->>AI: Generate 1536-d embedding for question text
    AI-->>API: Query vector
    API->>DB: Hybrid Search (Reciprocal Rank Fusion):<br/>1. Vector cosine distance query (pgvector)<br/>2. Full-text search match (tsvector)<br/>FILTER BY: user department visibility & confirmed documents
    DB-->>API: Top ranked retrieved chunks with page numbers
    alt No chunks meet relevance threshold (floor = 0.50)
        API-->>Web: Friendly refusal ("Could not find relevant information...")
    else Relevant chunks retrieved
        API->>AI: Synthesize grounded answer citing document name & page
        AI-->>API: Answer text with citations
        API->>API: Verify citation grounding (check citations exist in retrieved chunks)
        API->>DB: Write redacted Q&A log (snippet hash only, no PII/secrets)
        API-->>Web: Verified answer with interactive document page citations
    end
```

---

## 3. Data Model Summary

The database schema is structured around procurement business workflows, automated extractions, approval chains, and an append-only audit trail:

| Table Name | Primary Key | Key Columns / Relationships | Purpose |
|---|---|---|---|
| `users` | UUID | `email`, `hashed_password`, `display_name`, `department_id`, `approval_limit_aed`, `is_active` | Staff identity and approval delegations |
| `user_roles` | Composite | `user_id`, `role` (`requester`, `buyer`, `manager`, `admin`, `intake`) | Role-based permission assignments |
| `departments` | UUID | `name` (`Facilities`, `IT`, `Projects`), `code` | Organizational division and row scoping |
| `vendors` | UUID | `name`, `odoo_id`, `trn`, `payment_terms_days`, `status` | Master vendor catalogue synced from ERP |
| `products` | UUID | `sku`, `name`, `category`, `unit_of_measure`, `unit_price_aed` | Standard product items catalogue |
| `purchase_requests` | UUID | `pr_number`, `title`, `department_id`, `created_by`, `status`, `total_estimated_aed` | Initial procurement request |
| `pr_lines` | UUID | `purchase_request_id`, `product_id`, `quantity`, `estimated_unit_price_aed` | Itemized line items on purchase request |
| `documents` | UUID | `filename`, `file_type`, `sha256_hash`, `blob_path`, `document_type`, `status`, `source` | Uploaded raw documents and ingestion status |
| `extractions` | UUID | `document_id`, `confidence_score`, `has_flags`, `has_suspicious_content`, `model_version` | AI extraction metadata and flags |
| `extracted_fields` | UUID | `extraction_id`, `field_name`, `field_value`, `confidence`, `bbox_json`, `page_number` | Field-level values with bounding-box coordinates |
| `extracted_lines` | UUID | `extraction_id`, `item_description`, `quantity`, `unit_price`, `total_amount`, `confidence` | Line-item grid extracted from document |
| `comparisons` | UUID | `pr_id`, `recommended_vendor_id`, `status`, `selected_vendor_id`, `override_reason` | Quote evaluation and decision record |
| `comparison_quotes` | UUID | `comparison_id`, `document_id`, `vendor_id`, `total_score`, `price_score`, `delivery_score` | Individual quote scoring breakdown |
| `purchase_orders` | UUID | `po_number`, `pr_id`, `comparison_id`, `vendor_id`, `total_amount_aed`, `status` | Formal commitment issued to supplier |
| `po_lines` | UUID | `purchase_order_id`, `line_number`, `description`, `quantity`, `unit_price_aed` | Committed order line items |
| `approval_steps` | UUID | `entity_type`, `entity_id`, `step_number`, `assigned_to`, `status`, `decision`, `decision_reason` | Sequential multi-tier approval workflow |
| `matches` | UUID | `po_id`, `delivery_note_id`, `invoice_id`, `status` (`matched`, `exception`, `escalated`) | Three-way match summary record |
| `match_lines` | UUID | `match_id`, `po_line_id`, `po_qty`, `dn_qty`, `inv_qty`, `unit_price_variance`, `status` | Line-level match comparison results |
| `match_exceptions` | UUID | `match_id`, `match_line_id`, `exception_type`, `status`, `assigned_role`, `resolution_action` | Tracked exceptions (e.g. qty variance, price) |
| `chunks` | UUID | `document_id`, `page_number`, `chunk_index`, `content`, `embedding` (`vector(1536)`), `ts_content` | Grounded semantic search chunks |
| `injection_flags` | UUID | `document_id`, `pattern_name`, `severity`, `snippet_hash`, `acknowledged_by` | Security audit of suspicious text |
| `qa_logs` | UUID | `user_id`, `question_hash`, `retrieved_chunk_count`, `was_refused`, `latency_ms` | Redacted telemetry for Q&A queries |
| `jobs` | UUID | `job_type`, `payload_json`, `status`, `retry_count`, `scheduled_at`, `locked_by` | Resilient background processing queue |
| `audit_log` | BigInt Identity | `sequence_id`, `timestamp`, `action`, `actor_id`, `correlation_id`, `payload`, `hash`, `prev_hash` | Append-only cryptographic hash chain |

---

## 4. Security Model

### 4.1 Role-Based Access Control (RBAC) & Scoping

Access permissions are enforced strictly on every API endpoint through the policy dependency (`PolicyChecker`). Scopes are evaluated across five distinct roles:

```mermaid
flowchart TD
    subgraph Roles["System Roles"]
        Req["Requester"]
        Buy["Buyer"]
        Mgr["Manager"]
        Adm["Admin"]
        Int["Intake Service"]
    end

    subgraph Boundaries["Functional Boundaries"]
        R_Req["Create & Submit PRs<br/>Department-Scoped Q&A"]
        R_Buy["Upload & Review Documents<br/>Execute Comparisons & POs<br/>Accept Non-Qty Exceptions <= AED 500"]
        R_Mgr["Approve Commitments within Limit<br/>Resolve Escalated Exceptions"]
        R_Adm["Manage Settings, Users & Tolerances<br/>View & Cryptographically Verify Audit Trail"]
        R_Int["Service Ingestion Only<br/>POST /api/v1/intake/email"]
    end

    Req --> R_Req
    Buy --> R_Buy
    Mgr --> R_Mgr
    Adm --> R_Adm
    Int --> R_Int
```

- **Row-Level Visibility**: Requesters and Buyers only access records belonging to their assigned department. Managers view items routed to their approval queue or within their department. Admins inspect system configuration and audit logs.
- **Segregation of Duties (SoD)**:
  - A user cannot approve their own Purchase Request or Purchase Order, even if their role permits approvals.
  - A Buyer cannot approve a Purchase Order they created.
  - Administrators cannot approve financial commitments (UI elements and API endpoints return 403 Forbidden).
  - Buyers cannot resolve over-billed quantity exceptions (must escalate to Manager).

### 4.2 Append-Only Cryptographic Audit Log

- Every state change writes an audit record in the **same database transaction** via `app.audit.service.record()`.
- Records are chained using SHA-256:
  `hash_n = SHA256(hash_{n-1} || sequence_id_n || action_n || actor_id_n || payload_n)`
- Database permissions revoke `UPDATE` and `DELETE` on the `audit_log` table, backed by a PostgreSQL trigger raising exceptions on any mutation attempt.
- The administrator can trigger on-demand cryptographic verification (`POST /api/v1/audit/verify`) to detect historical record tampering.

### 4.3 Prompt-Injection Defence-in-Depth

The application treats document text as **untrusted data, never instructions**:
1. **Rule-Based Pre-Scanner (`app/extraction/injection_detector.py`)**:
   - Inspects raw text against 32+ prompt injection patterns (e.g. `ignore previous instructions`, `system prompt override`, `set total to 0`, `role: system`).
   - Flags suspicious documents, creates an `injection_flags` record, and raises a visible warning banner in the review UI.
2. **Deterministic Shielding**:
   - The AI model never decides actions, approves vouchers, or triggers payments.
   - Text passed to LLM prompts is strictly delimited within `<untrusted_document_data>` XML tags with system prompts directing the model to ignore instructions inside delimiters.
   - Output parsing strictly enforces JSON schemas with Pydantic validation.
3. **Review Block**:
   - Documents with active suspicious content flags are blocked from confirmation until an authorized Buyer explicitly acknowledges the warning and enters a logged justification.
4. **Privacy & Redaction**:
   - Prompt injection snippets are logged only as SHA-256 hashes with page indices; raw attack payloads are never reflected in application logs.

### 4.4 Secrets & Identity Management

- **Zero Hardcoded Secrets**: Secrets are absent from all source code, Dockerfiles, and repository commits.
- **Production Key Vault**: Managed identities (`id-pda-prod-uaen`) authenticate to Azure Key Vault using Azure RBAC (`Key Vault Secrets User`).
- **Managed Identity for Storage & AI**: Azure Storage and Azure OpenAI / Document Intelligence authenticate via Microsoft Entra User-Assigned Managed Identity, eliminating storage connection strings and Cognitive Services API keys in cloud deployments.

---

## 5. Observability & Telemetry

1. **Distributed Tracing (OpenTelemetry)**:
   - Tracing instruments the Next.js BFF, FastAPI API endpoints, database queries, and async worker jobs.
   - Traces are exported to Azure Application Insights via the `azure-monitor-opentelemetry` exporter.
2. **Correlation ID Propagation**:
   - Every inbound HTTP request receives a unique `X-Request-ID` header (generated by Next.js BFF or FastAPI middleware).
   - The correlation ID is propagated to async job queue payloads, background worker processes, and recorded inside the audit trail for cross-tier root-cause analysis.
3. **Structured Logging & Redaction**:
   - Logs are formatted as structured JSON with log levels, timestamps, request IDs, and module names.
   - PII and document content (such as raw invoice text or vendor bank details) are automatically stripped by the redaction filter (`app.core.logging.RedactionFilter`).

---

## 6. Cloud Deployment Topology

The production architecture is deployed in **UAE North (`uaenorth`)** using Azure Infrastructure-as-Code (Bicep):

> **Demo-only exception: PostgreSQL region.** For this demo the database runs in **North Europe** (`postgresLocation=northeurope`), while everything else stays in UAE North. The demo subscription is not offered Burstable PostgreSQL Flexible Server SKUs in UAE North (`SkuNotAvailable` for B1ms and B2s), and General Purpose would break the demo budget. All data in the demo is synthetic (fake vendors and documents), so data residency does not apply. A real Brilliant deployment would keep PostgreSQL in UAE North (leave `postgresLocation` at its default) on a subscription with that SKU, or use General Purpose.

```mermaid
flowchart TB
    subgraph Internet["Public Internet"]
        Users["Procurement Staff & Approvers"]
    end

    subgraph Azure_UAENorth["Azure Region: UAE North (uaenorth)"]
        subgraph RG_Prod["Resource Group: rg-pda-prod-uaen"]
            subgraph ACA_Env["Container Apps Environment (Consumption)"]
                CA_Web["ca-web-pda-prod-uaen<br/>Port 3000 | External Ingress | 0-1 Replicas"]
                CA_API["ca-api-pda-prod-uaen<br/>Port 8000 | Internal VNet Ingress | 0-1 Replicas"]
                CA_Worker["ca-worker-pda-prod-uaen<br/>No Ingress | 1 Replica"]
                Job_Migrate["migrate<br/>Manual Container App Job (Alembic + Seed)"]
            end

            KV["Azure Key Vault<br/>kv-pda-prod-uaen<br/>RBAC Mode | Secure Secrets"]
            Storage["Azure Storage Account<br/>stpdaproduaen<br/>TLS 1.2 | Private 'documents' Container"]
            Postgres["Azure PostgreSQL Flexible Server<br/>psql-pda-prod-uaen<br/>Standard_B1ms | pgvector | DB: pda<br/>(demo: North Europe)"]
            AppInsights["Application Insights<br/>appi-pda-prod-uaen"]
            LogAnalytics["Log Analytics Workspace<br/>log-pda-prod-uaen"]
            ManagedID["User-Assigned Managed Identity<br/>id-pda-prod-uaen"]
        end

        subgraph RG_AI["Resource Group: rg-pda-ai-uaen (live AI mode only)"]
            OpenAI["Azure OpenAI Service<br/>oai-pda-ai-uaen<br/>Chat (default gpt-5-mini) & text-embedding-3-small"]
            DocIntel["Azure Document Intelligence<br/>di-pda-ai-uaen<br/>SKU F0"]
        end

        subgraph Budget_Sub["Subscription Scope"]
            Budget["Cost Budget<br/>Alerts at 50% & 100%"]
        end
    end

    Users -->|HTTPS / Port 443| CA_Web
    CA_Web -->|Internal HTTP| CA_API
    CA_API --> Postgres
    CA_API --> Storage
    CA_Worker --> Postgres
    CA_Worker --> Storage
    CA_Worker -.->|Managed Identity Auth| OpenAI
    CA_Worker -.->|Managed Identity Auth| DocIntel
    ManagedID -.->|Key Vault Secrets User| KV
    ManagedID -.->|Storage Blob Data Contributor| Storage
    ManagedID -.->|Cognitive Services User| OpenAI
    ManagedID -.->|Cognitive Services User| DocIntel
    ACA_Env --> LogAnalytics
    CA_Web -.-> AppInsights
    CA_API -.-> AppInsights
    CA_Worker -.-> AppInsights
```
