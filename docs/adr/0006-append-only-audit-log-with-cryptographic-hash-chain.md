# 6. Append-Only Audit Log with Cryptographic Hash Chain

- **Status:** Accepted
- **Date:** 2026-11-19

## Context
Procurement transactions require strict accountability, regulatory compliance, and tamper-evident records. Database administrators or malicious actors with table access could silently alter records or delete compliance history unless cryptographic tamper-proofing is established.

## Decision
Implement an append-only audit log table (`audit_log`) where every row records action metadata, actor identity, request correlation ID, timestamp, and payload. Each record includes a SHA-256 cryptographic hash (`hash = SHA256(prev_hash + sequence_id + payload)`), forming an unbroken cryptographic hash chain. Database role privileges revoke `UPDATE` and `DELETE` on the table, enforced by a PostgreSQL trigger.

## Consequences
- **Positive:** Any alteration, insertion, or deletion of historical audit entries breaks the cryptographic hash chain and is immediately flagged by the verification algorithm; full non-repudiation and compliance readiness; CSV export for external review.
- **Negative:** Audit row insertion requires sequential locking on hash generation to ensure linear ordering; storage volume continuously grows, requiring archiving strategies over extended multi-year periods.
