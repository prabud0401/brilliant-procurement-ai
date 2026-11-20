#!/usr/bin/env bash
set -euo pipefail

# scripts/deploy.sh
# Manual deployment helper for Brilliant Procurement AI infrastructure.
# Runs 'what-if' first to preview changes, then creates or updates resources upon confirmation.
# Written for operator guidance; not executed automatically during build/tests.

usage() {
  echo "Usage: $0 [env] [gate] [--yes]"
  echo "  env:   Target environment (e.g. prod, dev; default: prod)"
  echo "  gate:  Deployment gate to run: 'g1' (budget + AI), 'g2' (main stack), or 'all' (default: all)"
  echo "  --yes: Non-interactive confirmation to proceed after what-if"
  exit 1
}

ENV="prod"
GATE="all"
AUTO_CONFIRM=false

for arg in "$@"; do
  case "$arg" in
    --yes|-y)
      AUTO_CONFIRM=true
      ;;
    g1|G1)
      GATE="g1"
      ;;
    g2|G2)
      GATE="g2"
      ;;
    all|ALL)
      GATE="all"
      ;;
    -h|--help)
      usage
      ;;
    *)
      if [ -n "$arg" ] && [ "${arg:0:1}" != "-" ]; then
        ENV="$arg"
      fi
      ;;
  esac
done

LOCATION="uaenorth"
MAIN_RG="rg-pda-${ENV}-uaen"
AI_RG="rg-pda-ai-uaen"

echo "=========================================================="
echo "Brilliant PDA Deployment Script (Dry Run & Deploy)"
echo "Environment: ${ENV}"
echo "Location:    ${LOCATION}"
echo "Gate:        ${GATE}"
echo "=========================================================="

# Ensure required secure variables are available or ask operator
check_secure_params() {
  if [ -z "${JWT_SECRET:-}" ]; then
    read -r -s -p "Enter JWT_SECRET (min 32 chars): " JWT_SECRET
    echo ""
  fi
  if [ -z "${POSTGRES_ADMIN_PASSWORD:-}" ]; then
    read -r -s -p "Enter POSTGRES_ADMIN_PASSWORD: " POSTGRES_ADMIN_PASSWORD
    echo ""
  fi
  if [ -z "${APP_DB_PASSWORD:-}" ]; then
    read -r -s -p "Enter APP_DB_PASSWORD: " APP_DB_PASSWORD
    echo ""
  fi
  if [ -z "${DEMO_USER_PASSWORD:-}" ]; then
    read -r -s -p "Enter DEMO_USER_PASSWORD: " DEMO_USER_PASSWORD
    echo ""
  fi
}

deploy_gate_1() {
  echo "----------------------------------------------------------"
  echo "Gate G1: Subscription Budget & AI Services"
  echo "----------------------------------------------------------"

  BUDGET_EMAIL="${BUDGET_ALERT_EMAIL:-admin@demo-holdings.example}"

  echo "[G1 Step 1] What-if for subscription budget..."
  az deployment sub what-if \
    --location "${LOCATION}" \
    --template-file "infra/budget.bicep" \
    --parameters alertEmail="${BUDGET_EMAIL}"

  if [ "$AUTO_CONFIRM" != "true" ]; then
    read -r -p "Apply subscription budget? (y/N): " CONFIRM_BUDGET
    if [[ ! "$CONFIRM_BUDGET" =~ ^[Yy]$ ]]; then
      echo "Skipping budget deployment."
    else
      az deployment sub create \
        --location "${LOCATION}" \
        --template-file "infra/budget.bicep" \
        --parameters alertEmail="${BUDGET_EMAIL}"
    fi
  else
    az deployment sub create \
      --location "${LOCATION}" \
      --template-file "infra/budget.bicep" \
      --parameters alertEmail="${BUDGET_EMAIL}"
  fi

  echo "[G1 Step 2] Ensuring AI resource group ${AI_RG} exists..."
  az group create --name "${AI_RG}" --location "${LOCATION}" --tags project=brilliant-pda owner=prabudeva

  echo "[G1 Step 3] What-if for AI services (Azure OpenAI + Document Intelligence)..."
  az deployment group what-if \
    --resource-group "${AI_RG}" \
    --template-file "infra/ai.bicep" \
    --parameters env="${ENV}" location="${LOCATION}"

  if [ "$AUTO_CONFIRM" != "true" ]; then
    read -r -p "Apply AI services deployment? (y/N): " CONFIRM_AI
    if [[ ! "$CONFIRM_AI" =~ ^[Yy]$ ]]; then
      echo "Skipping AI services deployment."
    else
      az deployment group create \
        --resource-group "${AI_RG}" \
        --template-file "infra/ai.bicep" \
        --parameters env="${ENV}" location="${LOCATION}"
    fi
  else
    az deployment group create \
      --resource-group "${AI_RG}" \
      --template-file "infra/ai.bicep" \
      --parameters env="${ENV}" location="${LOCATION}"
  fi
}

deploy_gate_2() {
  echo "----------------------------------------------------------"
  echo "Gate G2: Core Environment Stack (${MAIN_RG})"
  echo "----------------------------------------------------------"

  check_secure_params

  echo "[G2 Step 1] Ensuring resource group ${MAIN_RG} exists..."
  az group create --name "${MAIN_RG}" --location "${LOCATION}" --tags project=brilliant-pda env="${ENV}" owner=prabudeva

  echo "[G2 Step 2] What-if preview for main infrastructure..."
  az deployment group what-if \
    --resource-group "${MAIN_RG}" \
    --template-file "infra/main.bicep" \
    --parameters \
      env="${ENV}" \
      location="${LOCATION}" \
      jwtSecret="${JWT_SECRET}" \
      postgresAdminPassword="${POSTGRES_ADMIN_PASSWORD}" \
      appDbPassword="${APP_DB_PASSWORD}" \
      demoUserPassword="${DEMO_USER_PASSWORD}" \
      containerRegistryPassword="${CONTAINER_REGISTRY_PASSWORD:-}" \
      enableEmailIntake="${ENABLE_EMAIL_INTAKE:-false}" \
      intakeKey="${INTAKE_KEY:-}"

  if [ "$AUTO_CONFIRM" != "true" ]; then
    read -r -p "Proceed with main stack deployment? (y/N): " CONFIRM_MAIN
    if [[ ! "$CONFIRM_MAIN" =~ ^[Yy]$ ]]; then
      echo "Main stack deployment aborted."
      return 0
    fi
  fi

  echo "[G2 Step 3] Creating main infrastructure deployment..."
  az deployment group create \
    --resource-group "${MAIN_RG}" \
    --template-file "infra/main.bicep" \
    --parameters \
      env="${ENV}" \
      location="${LOCATION}" \
      jwtSecret="${JWT_SECRET}" \
      postgresAdminPassword="${POSTGRES_ADMIN_PASSWORD}" \
      appDbPassword="${APP_DB_PASSWORD}" \
      demoUserPassword="${DEMO_USER_PASSWORD}" \
      containerRegistryPassword="${CONTAINER_REGISTRY_PASSWORD:-}" \
      enableEmailIntake="${ENABLE_EMAIL_INTAKE:-false}" \
      intakeKey="${INTAKE_KEY:-}"

  echo "[G2 Step 4] Triggering database migration and seed job..."
  az containerapp job start --name migrate --resource-group "${MAIN_RG}"
  echo "Migration job initiated."
}

if [ "$GATE" = "g1" ] || [ "$GATE" = "all" ]; then
  deploy_gate_1
fi

if [ "$GATE" = "g2" ] || [ "$GATE" = "all" ]; then
  deploy_gate_2
fi

echo "Deploy execution completed."
