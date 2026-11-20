# 3. Deterministic Rules Decide, AI Only Extracts and Explains

- **Status:** Accepted
- **Date:** 2026-11-19

## Context
Autonomous LLM agents face hallucination risks, non-deterministic decision paths, and susceptibility to indirect prompt injection. Allowing AI models to approve financial commitments, alter purchase totals, or route approvals introduces compliance, audit, and security vulnerabilities.

## Decision
Enforce strict separation between deterministic business code and AI capabilities. AI models are exclusively utilized for parsing document text/layout into structured schemas, generating plain-language explanations of deterministic comparison scores, and retrieving cited answers. All arithmetic validations, approval limits, tolerance evaluations, and state transitions are executed by deterministic Python algorithms. Explanations are verified by a faithfulness checker against source facts JSON.

## Consequences
- **Positive:** Financial calculations, segregation of duties, and approval thresholds are 100% reproducible, verifiable, and auditable; prompt injections cannot alter decision state; system complies with corporate procurement governance.
- **Negative:** Recommendation explanations require an additional verification pass with template fallbacks if unfaithful; new business rules must be implemented in code rather than prompted.
