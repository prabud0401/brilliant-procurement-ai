#!/usr/bin/env bash
# scripts/smoke.sh - Smoke test script for PDA deployment pipeline (prompts/R11.md, NFR-REL-01)
# Usage: ./scripts/smoke.sh [BASE_URL]
# Exit code 0 if all checks pass, 1 on any failure.

set -euo pipefail

BASE_URL="${1:-${WEB_BASE_URL:-http://localhost:3000}}"
# Strip trailing slash
BASE_URL="${BASE_URL%/}"

COOKIE_JAR=$(mktemp)
trap 'rm -f "$COOKIE_JAR"' EXIT

echo "=== PDA Smoke Test Suite ==="
echo "Target URL: $BASE_URL"

# 1. Check /healthz (via web)
echo -n "Checking /healthz... "
HEALTH_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/healthz" || echo "000")
if [ "$HEALTH_CODE" != "200" ]; then
  echo "FAILED (HTTP $HEALTH_CODE)"
  exit 1
fi
echo "OK (HTTP 200)"

# 2. Check /readyz (via web)
echo -n "Checking /readyz... "
READY_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/readyz" || echo "000")
if [ "$READY_CODE" != "200" ]; then
  echo "FAILED (HTTP $READY_CODE)"
  exit 1
fi
echo "OK (HTTP 200)"

# 3. Check sign-in page 200
echo -n "Checking sign-in page (/login)... "
LOGIN_PAGE_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/login" || echo "000")
if [ "$LOGIN_PAGE_CODE" != "200" ]; then
  echo "FAILED (HTTP $LOGIN_PAGE_CODE)"
  exit 1
fi
echo "OK (HTTP 200)"

# 4. Check /api/v1/me 401 without token/session
echo -n "Checking /api/v1/me returns 401 without token... "
UNAUTH_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL/api/v1/me" || echo "000")
if [ "$UNAUTH_CODE" != "401" ]; then
  echo "FAILED (Expected 401, got HTTP $UNAUTH_CODE)"
  exit 1
fi
echo "OK (HTTP 401)"

# 5. Authenticate with demo user and verify /api/v1/me 200
DEMO_EMAIL="${DEMO_USER_EMAIL:-requester.fac@demo-holdings.example}"
DEMO_PASS="${DEMO_USER_PASSWORD:-demo_password_123}"

# If .env exists in current or parent directory and DEMO_USER_PASSWORD not set, load it
if [ -z "${DEMO_USER_PASSWORD:-}" ]; then
  if [ -f .env ]; then
    DEMO_PASS=$(grep -E '^DEMO_USER_PASSWORD=' .env | cut -d '=' -f2- | tr -d '"'\''\r' || echo "$DEMO_PASS")
  elif [ -f ../.env ]; then
    DEMO_PASS=$(grep -E '^DEMO_USER_PASSWORD=' ../.env | cut -d '=' -f2- | tr -d '"'\''\r' || echo "$DEMO_PASS")
  fi
fi

echo -n "Signing in as $DEMO_EMAIL... "
LOGIN_RESP=$(curl -s -w "\n%{http_code}" -c "$COOKIE_JAR" \
  -H "Content-Type: application/json" \
  -H "Origin: $BASE_URL" \
  -X POST "$BASE_URL/api/v1/auth/login" \
  -d "{\"email\":\"$DEMO_EMAIL\",\"password\":\"$DEMO_PASS\"}")

LOGIN_CODE=$(echo "$LOGIN_RESP" | tail -n1)
if [ "$LOGIN_CODE" != "200" ]; then
  echo "FAILED (HTTP $LOGIN_CODE)"
  echo "Response: $(echo "$LOGIN_RESP" | head -n-1)"
  exit 1
fi
echo "OK (HTTP 200)"

# 6. Check /api/v1/me 200 with session cookie
echo -n "Checking /api/v1/me with authenticated session... "
ME_RESP=$(curl -s -w "\n%{http_code}" -b "$COOKIE_JAR" "$BASE_URL/api/v1/me")
ME_CODE=$(echo "$ME_RESP" | tail -n1)
ME_BODY=$(echo "$ME_RESP" | head -n-1)

if [ "$ME_CODE" != "200" ]; then
  echo "FAILED (HTTP $ME_CODE)"
  exit 1
fi

if ! echo "$ME_BODY" | grep -q "$DEMO_EMAIL"; then
  echo "FAILED (Response did not contain user email: $ME_BODY)"
  exit 1
fi
echo "OK (HTTP 200)"

echo "=== All smoke checks passed successfully! ==="
exit 0
