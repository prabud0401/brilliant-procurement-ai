# 9. Email Intake via Azure Logic Apps

- **Status:** Accepted
- **Date:** 2026-11-19

## Context
Suppliers commonly deliver quotations, delivery notes, and invoices via email attachments rather than web portals. The application requires an automated email intake channel that mirrors enterprise Microsoft 365 / Power Automate architectures without requiring premature enterprise tenant integration.

## Decision
Implement email intake using an Azure Logic App (Consumption) connected to a dedicated demo Outlook.com mailbox (`infra/logicapp/logicapp.bicep`). The Logic App polls every 5 minutes for new messages with attachments, filters files by MIME type (PDF, PNG, JPEG) and size limit (<= 4 MB), and securely forwards approved attachments via HTTPS to `POST /api/v1/intake/email` using a shared service key authenticated against a hashed secret stored in Key Vault.

## Consequences
- **Positive:** Fully automated document intake mirroring enterprise Power Automate workflows; logic app secures input/output payloads in run history; documents enter the standard queue tagged with source `email` and full audit metadata.
- **Negative:** Requires one-time interactive OAuth sign-in to the demo mailbox via the Outlook API Connection at deployment gate G2; consumption polling introduces up to a 5-minute intake latency.
