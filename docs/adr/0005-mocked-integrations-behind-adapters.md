# 5. Mocked Integrations Behind Typed Adapters

- **Status:** Accepted
- **Date:** 2026-11-19

## Context
The procurement assistant interacts with external corporate systems: Odoo ERP for vendor master data and purchase order sync, SharePoint for document storage, and Microsoft Teams via Power Automate for notifications. Connecting live enterprise tenants during initial development and evaluation poses security, provisioning, and environment dependency challenges.

## Decision
Place all external system interactions behind typed adapter interfaces in `services/backend/app/integrations/` (`OdooAdapter`, `SharePointAdapter`, `PowerAutomateAdapter`, `IdentityAdapter`). Provide in-memory mock implementations loaded by default (`INTEGRATIONS_MODE=mock`), seeded with realistic synthetic data, and clearly labelled in the administration user interface.

## Consequences
- **Positive:** Complete local developer independence without external cloud or ERP dependencies; predictable test assertions for end-to-end integration flows; straightforward path to plug in live REST/OAuth connectors post-demo.
- **Negative:** Live ERP nuances (such as remote rate limiting or eventual consistency) are not exercised in the mock environment; bidirectional live sync remains a post-demo backlog item.
