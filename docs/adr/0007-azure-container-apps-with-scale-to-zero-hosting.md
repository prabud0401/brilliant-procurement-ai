# 7. Azure Container Apps with Scale-to-Zero Hosting

- **Status:** Accepted
- **Date:** 2026-11-19

## Context
The application needs modern cloud hosting with automated TLS, domain routing, background worker scaling, and health monitoring. Dedicated Kubernetes clusters (AKS) introduce substantial infrastructure complexity, operational maintenance, and high idle runtime costs.

## Decision
Deploy the solution to Azure Container Apps (ACA) on Consumption workload profiles in `uaenorth`. Three container apps are configured:
1. `ca-web`: Next.js BFF with external HTTPS ingress, scaling 0 to 1 replica.
2. `ca-api`: FastAPI backend with internal VNet ingress, scaling 0 to 1 replica.
3. `ca-worker`: Asynchronous extraction/matching worker, min 1 replica to process jobs promptly.
A Container Apps Job handles Alembic schema migrations on deployment.

## Consequences
- **Positive:** Serverless billing model allows web and API tiers to scale to zero when idle, minimizing ongoing cloud expenses; built-in ingress, automatic TLS, and managed identity integration; simplified deployment without Kubernetes manifest overhead.
- **Negative:** Scale-from-zero cold starts introduce minor latency on initial requests after idle periods; worker requires at least 1 active replica to prevent delayed asynchronous queue processing.
