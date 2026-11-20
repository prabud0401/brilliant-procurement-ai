#!/usr/bin/env bash
set -euo pipefail

# scripts/teardown.sh
# One-command teardown for Brilliant Procurement AI hosted demo infrastructure.
# Deletes resource groups, purges soft-deleted Key Vault and Cognitive Services accounts,
# and verifies that no lingering resources tagged project=brilliant-demo remain.

usage() {
  echo "Usage: $0 <env> [--yes]"
  echo "  <env>   Environment name (e.g. prod, dev)"
  echo "  --yes   Skip confirmation prompt (required for non-interactive / CI runs)"
  exit 1
}

if [ "$#" -lt 1 ]; then
  usage
fi

ENV="$1"
shift

AUTO_CONFIRM=false
while [ "$#" -gt 0 ]; do
  case "$1" in
    --yes|-y)
      AUTO_CONFIRM=true
      shift
      ;;
    *)
      echo "Unknown option: $1"
      usage
      ;;
  esac
done

MAIN_RG="${MAIN_RG:-rg-brilliant-demo-${ENV}}"
AI_RG="${AI_RG:-rg-brilliant-demo}"
KV_NAME="kv-pda-${ENV}-uaen"
LOCATION="uaenorth"

echo "=========================================================="
echo "Brilliant PDA Teardown Script"
echo "Environment: ${ENV}"
echo "Resource Groups: ${MAIN_RG}, ${AI_RG}"
echo "Key Vault to purge: ${KV_NAME}"
echo "Location: ${LOCATION}"
echo "=========================================================="

if [ "$AUTO_CONFIRM" != "true" ]; then
  echo "WARNING: This will permanently destroy all resources in ${MAIN_RG} and ${AI_RG}."
  read -r -p "Type 'DELETE' to confirm teardown: " CONFIRMATION
  if [ "$CONFIRMATION" != "DELETE" ]; then
    echo "Teardown aborted by user."
    exit 1
  fi
fi

# 1. Delete main environment resource group if it exists
# Note: This permanently deletes all environment resources including Container Apps,
# PostgreSQL Flexible Server, Storage Account, Key Vault, and (if email intake was enabled)
# the Logic App workflow and Outlook API Connection.
if az group exists --name "${MAIN_RG}" 2>/dev/null | grep -q "true"; then
  echo "Deleting resource group: ${MAIN_RG} (including email intake Logic App and Outlook connection if deployed)..."
  az group delete --name "${MAIN_RG}" --yes
  echo "Resource group ${MAIN_RG} deleted."
else
  echo "Resource group ${MAIN_RG} does not exist, skipping."
fi

# 2. Delete AI resource group if it exists
if az group exists --name "${AI_RG}" 2>/dev/null | grep -q "true"; then
  echo "Deleting AI resource group: ${AI_RG}..."
  az group delete --name "${AI_RG}" --yes
  echo "Resource group ${AI_RG} deleted."
else
  echo "Resource group ${AI_RG} does not exist, skipping."
fi

# 3. Purge soft-deleted Key Vault so teardown leaves nothing behind
echo "Checking for soft-deleted Key Vault: ${KV_NAME}..."
DELETED_KV=$(az keyvault list-deleted --query "[?name=='${KV_NAME}'].name" -o tsv 2>/dev/null || true)
if [ -n "${DELETED_KV}" ]; then
  echo "Purging soft-deleted Key Vault: ${KV_NAME} in ${LOCATION}..."
  az keyvault purge --name "${KV_NAME}" --location "${LOCATION}" || true
  echo "Key Vault ${KV_NAME} purged."
else
  echo "No soft-deleted Key Vault found matching ${KV_NAME}."
fi

# 4. Purge soft-deleted Cognitive Services accounts
echo "Checking for soft-deleted Cognitive Services accounts..."
DELETED_COG_ACCOUNTS=$(az cognitiveservices account list-deleted --query "[?contains(name, 'pda') || contains(name, 'brilliant-demo')].name" -o tsv 2>/dev/null || true)
if [ -n "${DELETED_COG_ACCOUNTS}" ]; then
  for cog in ${DELETED_COG_ACCOUNTS}; do
    echo "Purging soft-deleted Cognitive Services account: ${cog} in ${LOCATION}..."
    az cognitiveservices account purge --name "${cog}" --location "${LOCATION}" --resource-group "${AI_RG}" 2>/dev/null || \
    az cognitiveservices account purge --name "${cog}" --location "${LOCATION}" 2>/dev/null || true
  done
fi

# 5. List anything still tagged project=brilliant-demo
echo "=========================================================="
echo "Checking for any remaining resources tagged project=brilliant-demo..."
echo "=========================================================="
REMAINING=$(az resource list --tag project=brilliant-demo --output table 2>/dev/null || true)

if [ -n "${REMAINING}" ] && [ "${REMAINING}" != "[]" ]; then
  echo "Remaining tagged resources found:"
  echo "${REMAINING}"
else
  echo "Clean! No lingering resources tagged project=brilliant-demo found."
fi

echo "Teardown complete for environment '${ENV}'."
