# Release Notes — Version 0.1.0-demo

- **Release Version:** `0.1.0-demo`
- **Release Date:** 20 November 2026
- **Target Audience:** Procurement & Technical Evaluation Panel, Brilliant Investment & Development
- **Status:** Release Candidate (Demo Build)

---

## 1. Overview

The **Procurement Document Assistant (PDA)** is an AI-assisted procurement and invoice processing system built for UAE corporate compliance (AED currency). It combines artificial intelligence document parsing, grounded semantic search, and deterministic financial controls:
- **AI where it helps:** Extracting structured fields from unstructured PDFs, computing confidence scores, finding visual bounding boxes, synthesizing cited answers, and explaining quote evaluations.
- **Deterministic code where it matters:** Arithmetic validation, VAT (5%) and TRN checks, multi-criteria comparison scoring, segregation of duties, approval routing, tolerance thresholds, and an append-only cryptographic audit trail.

---

## 2. What's Included in This Release

This release implements all 19 Must-have user stories and the stretch email intake integration:

### 2.1 Document Ingestion & AI Extraction
- **US-01 (File Validation):** Secure file upload supporting PDF, PNG, and JPEG up to 10 MB. Implements MIME type inspection, SHA-256 duplicate detection, and page count checks. Untyped and email-intake documents are auto-classified after OCR and before extraction.
- **US-02 (Extraction Pipeline):** Automated extraction of vendor names, TRNs, document numbers, line items, quantities, unit prices, subtotal, VAT, and total amounts with bounding-box coordinates and confidence scores.
- **US-03 (Human-in-the-Loop Review):** Split-screen review interface displaying the original document with interactive canvas bounding-box overlays alongside editable extracted fields. Open items must be resolved before confirmation.
- **US-04 (Procurement Validation Rules):** Automated checks for line-item sum reconciliation, UAE 5% VAT calculations, valid UAE TRN format, and logical date sequencing.

### 2.2 Quote Comparison & Procurement Flow
- **US-08 (Side-by-Side Matrix):** Comparative evaluation grid for 2 to 5 competing quotations linked to a purchase request.
- **US-09 (Deterministic Scoring & Explanation):** Multi-criteria weighted scoring algorithm (60% price, 20% delivery speed, 10% payment terms, 10% warranty). AI synthesizes a plain-language summary verified by a deterministic faithfulness checker against source facts JSON.
- **US-10 (Decision & Purchase Order Creation):** Buyer selects winning vendor or enters a mandatory override justification (≥ 10 characters). Automatically generates a structured Purchase Order.

### 2.3 Three-Way Matching & Exceptions
- **US-13 (Line-Level Match):** Automated three-way reconciliation across Purchase Order, Delivery Note, and Vendor Invoice with configurable price and quantity tolerances. Displays PO line description fallback and invoice unit price accurately.
- **US-14 (Exception Queue):** Automated categorization of discrepancies (quantity variance, price discrepancy, missing delivery receipt).
- **US-15 (Exception Resolution):** Tiered resolution workflow: Buyers can accept minor non-quantity discrepancies up to AED 500.00; over-billed quantities are locked from Buyer acceptance and must be escalated to the department Manager. Default queue filter displays all unresolved items (open and escalated).
- **PO VAT Percentage Display:** Renders fractional VAT rates (e.g. 0.05) formatted as 5% across purchase order details.

### 2.4 Document Assistant Q&A
- **US-17 (Cited Q&A):** Natural-language conversational interface answering queries grounded exclusively in confirmed procurement documents with document and page citations.
- **US-18 (Grounded Retrieval & Refusal):** Hybrid search combining pgvector semantic search and PostgreSQL full-text search with Reciprocal Rank Fusion. Implements a relevance floor (0.50) that gracefully refuses unanswerable or out-of-scope queries.
- **US-19 (Scoping & Privacy):** Q&A document chunk retrieval is strictly partitioned by user departmental role and visibility.
- **US-20 (Deep-Link Citation Page Anchors):** Interactive citation links in Q&A answers open the cited document and navigate directly to the referenced page in the split-screen viewer.

### 2.5 Approvals & Governance
- **US-21 (Approval Routing):** Multi-tier approval routing based on financial thresholds: Tier 1 (≤ AED 5,000), Tier 2 (AED 5,000.01 – 50,000), and Tier 3 (> AED 50,000).
- **US-22 (One-Screen Approval Bundle):** Comprehensive summary screen for approvers displaying line items, budget check, selected quote, and comparison facts.
- **US-23 (Segregation of Duties):** Strict business rule enforcement: requesters cannot approve their own requests; buyers cannot approve purchase orders they generated; system administrators cannot approve financial commitments.
- **US-24 (Append-Only Cryptographic Audit Log):** Tamper-evident audit trail with SHA-256 hash chaining. Database triggers prevent update and deletion. Includes in-app hash chain verification and CSV export.
- **US-25 (System Administration):** Administrative consoles for user roles, department approval limits, and match tolerance configurations.
- **US-29 (Prompt-Injection Defence):** Rule-based pre-scanner detecting 32+ injection patterns, XML delimiter isolation, red alert warning banner, and mandatory Buyer acknowledgement before document confirmation.

### 2.6 Stretch Feature (R13)
- **Email Intake via Logic Apps:** Automated ingestion channel connecting a demo Outlook.com mailbox to `POST /api/v1/intake/email` using a shared service key authenticated against Key Vault.

---

## 3. Known Limits & Design Boundaries

The following architectural constraints apply to the demo release:

1. **Seeded Password Authentication:** The application uses JWT session authentication with seeded role accounts rather than Microsoft Entra ID SSO.
2. **Mocked Enterprise Integrations:** Adapters for Odoo ERP, SharePoint, and Power Automate run using in-memory mock stores populated with synthetic data.
3. **Reduced Evaluation Benchmark:** The offline evaluation harness runs against 20 representative documents, 30 questions, and 32 injection cases to optimize pipeline execution speed.
4. **Replay Mode Default:** The repository is configured to `AI_PROVIDER=replay` out of the box, allowing full local execution and testing without Azure credentials.
5. **Fixed Scoring Weights:** Quote comparison weights are fixed at 60/20/10/10 rather than customizable per category.
6. **Single Delivery Note per PO:** Demo scenarios assume one primary delivery note per purchase order rather than complex partial shipment consolidation.

---

## 4. "After the Demo" Backlog

The following capabilities are scheduled for post-demo enterprise hardening per Sprint Plan Section 3.2:

| Story ID | Description | Planned Implementation |
|---|---|---|
| **US-05** | Vendor match to live Odoo vendor list | Connect Odoo adapter to live XML-RPC/JSON-RPC endpoint |
| **US-06** | Duplicate warning by vendor and invoice number | Cross-document soft duplicate alert across historical records |
| **US-07** | SharePoint folder import connector | Microsoft Graph API connector for automated document polling |
| **US-11** | Adjustable category scoring weights | Category-specific weighting profiles configured via Admin UI |
| **US-12** | Gap flags (expired quotes, currency, missing TRN) | Enhanced pre-review gap warning banners |
| **US-16** | Complex partial delivery matching | Multi-delivery note rollup and line item consolidation |
| **US-26** | Teams notifications via Power Automate | Webhook dispatch to Power Automate flow on pending approvals |
| **US-27** | Synchronize approved PO to Odoo ERP | Direct writeback of approved purchase orders to Odoo backend |
| **US-28** | Microsoft Entra ID Single Sign-On | OpenID Connect integration for corporate tenant login |
| **AIQ-Full** | Full-scale evaluation dataset | Expansion to 40 documents, 60 questions, and 10 degraded scans |

---

## 5. Known Issues Observed During Run

None beyond the known limits listed above.
