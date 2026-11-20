# 8. GitHub Actions OIDC Deployment with Public GHCR Images

- **Status:** Accepted
- **Date:** 2026-11-19

## Context
Deploying containers to Azure Container Apps requires storing container images in a registry and authenticating the deployment workflow to Azure. Storing long-lived cloud credentials (service principal client secrets) inside GitHub repository secrets creates security risks. Additionally, Azure Container Apps scaling nodes need reliable image pull access without transient token expiration failures.

## Decision
Configure OpenID Connect (OIDC) federated credentials between GitHub Actions and Microsoft Entra ID (`azure/login`), eliminating long-lived Azure secrets. Build and publish container images to GitHub Container Registry (GHCR) marked with public visibility, allowing Container Apps to pull revisions directly without credential caching issues.

## Consequences
- **Positive:** Zero long-lived cloud credentials stored in GitHub repository; automated token exchange per workflow execution; simplified container registry access for Azure Container Apps nodes without Azure Container Registry (ACR) basic tier cost.
- **Negative:** Container images in GHCR are publicly readable (requiring strict enforcement that no proprietary secrets, private models, or confidential data are ever baked into images); initial registry visibility toggle must be set to public.
