# 1. FastAPI and Next.js Backend-For-Frontend (BFF)

- **Status:** Accepted
- **Date:** 2026-11-19

## Context
The Procurement Document Assistant requires a responsive, accessible user interface for procurement staff alongside a typed, secure API for document extraction, validation, and workflow state transitions. Directly exposing backend JWT tokens to browser client JavaScript increases XSS token exfiltration risks and complicates cookie session handling.

## Decision
Adopt a decoupled architecture consisting of a Python FastAPI backend (`services/backend`) and a Next.js App Router front-end (`apps/web`) operating as a Backend-For-Frontend (BFF). The Next.js BFF proxy stores authentication tokens in secure, `httpOnly`, `SameSite=Lax` cookies, stripping tokens before sending responses to browser scripts.

## Consequences
- **Positive:** Browser JavaScript cannot access raw authentication tokens; clear separation between presentation logic and business processing; backend remains a stateless REST API suitable for CLI, worker, and automation intake.
- **Negative:** Requires running and deploying two separate web application processes (`web` and `api`); slight network latency overhead for requests proxied through the BFF layer.
