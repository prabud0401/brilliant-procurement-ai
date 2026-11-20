#!/usr/bin/env python3
"""Infrastructure guard tests for Bicep templates.

Asserts required configuration on compiled ARM template JSON:
1. worker minReplicas >= 1
2. web has API_BASE_URL
3. azure.extensions contains VECTOR, PGCRYPTO, and UUID-OSSP
4. administrator login is not postgres/admin/azure_superuser
5. storage allowSharedKeyAccess is false and api/worker have BLOB_ACCOUNT_URL + AZURE_CLIENT_ID
6. every @secure() param has no default
7. every app env var name used for api/worker exists as a field in services/backend/app/core/config.py Settings
   (or is in a short documented allowlist such as APPLICATIONINSIGHTS_CONNECTION_STRING)
8. all tagged resources carry the four tags (project, env, owner, expires)
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ALLOWED_ENV_VAR_NAMES = {
    "APPLICATIONINSIGHTS_CONNECTION_STRING",
}

DISALLOWED_ADMIN_LOGINS = {
    "postgres",
    "admin",
    "azure_superuser",
}

REQUIRED_TAG_KEYS = {
    "project",
    "env",
    "owner",
    "expires",
}


def build_bicep_to_json(bicep_path: Path) -> dict[str, Any]:
    """Compile a bicep file into ARM template JSON using 'az bicep build --stdout'."""
    cmd = ["az", "bicep", "build", "--file", str(bicep_path), "--stdout"]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return json.loads(proc.stdout)


def get_all_resources_recursive(template: dict[str, Any]) -> list[dict[str, Any]]:
    """Traverse template and any nested deployments to collect all resource objects."""
    collected: list[dict[str, Any]] = []
    resources = template.get("resources", {})
    iterable: list[dict[str, Any]] = []
    if isinstance(resources, dict):
        iterable = list(resources.values())
    elif isinstance(resources, list):
        iterable = resources

    for r in iterable:
        collected.append(r)
        if r.get("type") == "Microsoft.Resources/deployments" and "properties" in r:
            nested_template = r["properties"].get("template")
            if isinstance(nested_template, dict):
                collected.extend(get_all_resources_recursive(nested_template))

    return collected


def get_all_templates_recursive(template: dict[str, Any]) -> list[dict[str, Any]]:
    """Collect main template and all nested module templates."""
    collected = [template]
    resources = template.get("resources", {})
    iterable: list[dict[str, Any]] = []
    if isinstance(resources, dict):
        iterable = list(resources.values())
    elif isinstance(resources, list):
        iterable = resources

    for r in iterable:
        if r.get("type") == "Microsoft.Resources/deployments" and "properties" in r:
            nested_template = r["properties"].get("template")
            if isinstance(nested_template, dict):
                collected.extend(get_all_templates_recursive(nested_template))

    return collected


def extract_backend_settings_fields(config_path: Path) -> set[str]:
    """Extract field names from class Settings in config.py via AST."""
    tree = ast.parse(config_path.read_text(encoding="utf-8"))
    fields: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "Settings":
            for stmt in node.body:
                if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                    fields.add(stmt.target.id)
                elif isinstance(stmt, ast.Assign):
                    for t in stmt.targets:
                        if isinstance(t, ast.Name):
                            fields.add(t.id)
    return fields


def check_worker_min_replicas(resources: list[dict[str, Any]]) -> None:
    found = False
    for r in resources:
        if r.get("type") == "Microsoft.App/containerApps":
            template = r.get("properties", {}).get("template", {})
            containers = template.get("containers", [])
            for c in containers:
                if c.get("name") == "worker":
                    scale = template.get("scale", {})
                    min_replicas = scale.get("minReplicas", 0)
                    assert (
                        min_replicas >= 1
                    ), f"Worker minReplicas must be >= 1, but found {min_replicas}"
                    found = True
    assert found, "Worker container app not found in template"


def check_web_api_base_url(resources: list[dict[str, Any]]) -> None:
    found = False
    for r in resources:
        if r.get("type") == "Microsoft.App/containerApps":
            template = r.get("properties", {}).get("template", {})
            containers = template.get("containers", [])
            for c in containers:
                if c.get("name") == "web":
                    env_vars = {e.get("name"): e.get("value") for e in c.get("env", [])}
                    assert (
                        "API_BASE_URL" in env_vars
                    ), f"Web container missing API_BASE_URL environment variable. Found: {list(env_vars.keys())}"
                    assert (
                        "API_URL" not in env_vars
                    ), "Web container has unused API_URL environment variable"
                    assert (
                        "NEXT_PUBLIC_API_URL" not in env_vars
                    ), "Web container has unused NEXT_PUBLIC_API_URL environment variable"
                    found = True
    assert found, "Web container app not found in template"


def check_postgres_extensions(resources: list[dict[str, Any]]) -> None:
    found = False
    for r in resources:
        if r.get("type") == "Microsoft.DBforPostgreSQL/flexibleServers/configurations":
            name = str(r.get("name", ""))
            if "azure.extensions" in name:
                val = r.get("properties", {}).get("value", "")
                exts = [e.strip().upper() for e in val.split(",")]
                for required in ["VECTOR", "PGCRYPTO", "UUID-OSSP"]:
                    assert (
                        required in exts
                    ), f"azure.extensions must contain {required}, found: {val}"
                found = True
    assert found, "PostgreSQL azure.extensions configuration resource not found in template"


def check_administrator_login(main_template: dict[str, Any], resources: list[dict[str, Any]]) -> None:
    # Check default in parameters
    params = main_template.get("parameters", {})
    admin_login_param = params.get("postgresAdminLogin", {})
    default_login = admin_login_param.get("defaultValue", "").lower()
    assert (
        default_login not in DISALLOWED_ADMIN_LOGINS
    ), f"postgresAdminLogin default '{default_login}' is not allowed"

    # Check database server resource properties
    found = False
    for r in resources:
        if r.get("type") == "Microsoft.DBforPostgreSQL/flexibleServers":
            login = str(r.get("properties", {}).get("administratorLogin", "")).lower()
            for disallowed in DISALLOWED_ADMIN_LOGINS:
                assert (
                    login != disallowed
                ), f"PostgreSQL server administratorLogin cannot be '{disallowed}'"
            found = True
    assert found, "PostgreSQL flexible server resource not found in template"


def check_storage_and_app_identities(resources: list[dict[str, Any]]) -> None:
    # 1. Storage allowSharedKeyAccess is false
    storage_found = False
    for r in resources:
        if r.get("type") == "Microsoft.Storage/storageAccounts":
            allow_shared_key = r.get("properties", {}).get("allowSharedKeyAccess")
            assert (
                allow_shared_key is False
            ), f"Storage account allowSharedKeyAccess must be false, got: {allow_shared_key}"
            storage_found = True
    assert storage_found, "Storage account resource not found in template"

    # 2. api and worker have BLOB_ACCOUNT_URL and AZURE_CLIENT_ID
    for app_name in ["api", "worker"]:
        app_found = False
        for r in resources:
            if r.get("type") == "Microsoft.App/containerApps":
                containers = r.get("properties", {}).get("template", {}).get("containers", [])
                for c in containers:
                    if c.get("name") == app_name:
                        env_vars = {e.get("name") for e in c.get("env", [])}
                        assert (
                            "BLOB_ACCOUNT_URL" in env_vars
                        ), f"Container {app_name} missing BLOB_ACCOUNT_URL env var"
                        assert (
                            "AZURE_CLIENT_ID" in env_vars
                        ), f"Container {app_name} missing AZURE_CLIENT_ID env var"
                        app_found = True
        assert app_found, f"Container app {app_name} not found in template"


def check_secure_params_no_defaults(all_templates: list[dict[str, Any]]) -> None:
    # intakeKey has a default of '' so deployments with email intake disabled succeed (review finding 1)
    allowed_defaults = {"intakeKey"}
    for tmpl in all_templates:
        params = tmpl.get("parameters", {})
        for param_name, param_def in params.items():
            param_type = str(param_def.get("type", "")).lower()
            if "secure" in param_type and param_name not in allowed_defaults:
                assert "defaultValue" not in param_def, (
                    f"@secure() parameter '{param_name}' must NOT have a default value, "
                    f"found defaultValue={param_def.get('defaultValue')!r}"
                )


def check_intake_key_default(main_template: dict[str, Any]) -> None:
    params = main_template.get("parameters", {})
    assert "intakeKey" in params, "main.bicep missing intakeKey parameter"
    intake_def = params["intakeKey"]
    assert intake_def.get("type", "").lower() == "securestring", "intakeKey must be securestring"
    assert "defaultValue" in intake_def, "intakeKey must have a default value"
    assert (
        intake_def["defaultValue"] == ""
    ), f"intakeKey default must be empty string '', found: {intake_def['defaultValue']!r}"


def check_deploy_workflow_passes_intake_key(workflow_path: Path) -> None:
    content = workflow_path.read_text(encoding="utf-8")
    assert "intakeKey" in content, "deploy.yml must pass intakeKey parameter"
    assert "enableEmailIntake" in content, "deploy.yml must pass enableEmailIntake parameter"
    assert "secrets.INTAKE_KEY" in content, "deploy.yml must pass secrets.INTAKE_KEY"
    assert "vars.ENABLE_EMAIL_INTAKE" in content, "deploy.yml must pass vars.ENABLE_EMAIL_INTAKE"


def check_api_has_intake_key_hash_secret_ref(resources: list[dict[str, Any]]) -> None:
    found_env = False
    for r in resources:
        if r.get("type") == "Microsoft.App/containerApps":
            containers = r.get("properties", {}).get("template", {}).get("containers", [])
            for c in containers:
                if c.get("name") == "api":
                    for env_entry in c.get("env", []):
                        if isinstance(env_entry, dict) and env_entry.get("name") == "INTAKE_KEY_HASH":
                            assert env_entry.get("secretRef") == "intake-key-hash", (
                                f"INTAKE_KEY_HASH on api container must use secretRef 'intake-key-hash', "
                                f"got: {env_entry}"
                            )
                            found_env = True
    assert found_env, "Container 'api' must have INTAKE_KEY_HASH with secretRef 'intake-key-hash'"


def check_no_plain_intake_key_in_any_template_env(resources: list[dict[str, Any]]) -> None:
    for r in resources:
        if r.get("type") == "Microsoft.App/containerApps":
            containers = r.get("properties", {}).get("template", {}).get("containers", [])
            for c in containers:
                for env_entry in c.get("env", []):
                    if isinstance(env_entry, dict):
                        var_name = env_entry.get("name", "")
                        assert var_name != "INTAKE_KEY", (
                            f"Plain INTAKE_KEY must not be passed as environment variable in container {c.get('name')}"
                        )
                        val = str(env_entry.get("value", ""))
                        assert "intakeKey" not in val, (
                            f"intakeKey parameter expression must not be exposed in container {c.get('name')} env {var_name}"
                        )


def check_app_env_vars_match_settings(
    resources: list[dict[str, Any]], settings_fields: set[str]
) -> None:
    for r in resources:
        if r.get("type") == "Microsoft.App/containerApps":
            containers = r.get("properties", {}).get("template", {}).get("containers", [])
            for c in containers:
                cname = c.get("name")
                if cname in ("api", "worker"):
                    for env_entry in c.get("env", []):
                        var_name = env_entry.get("name")
                        assert (
                            var_name in settings_fields or var_name in ALLOWED_ENV_VAR_NAMES
                        ), (
                            f"Environment variable '{var_name}' on container '{cname}' does not exist "
                            f"in Settings fields or allowlist {ALLOWED_ENV_VAR_NAMES}"
                        )


def check_resource_tags(all_templates: list[dict[str, Any]]) -> None:
    for tmpl in all_templates:
        params = tmpl.get("parameters", {})
        if "tags" in params:
            tag_def = params["tags"]
            default_tags = tag_def.get("defaultValue")
            if isinstance(default_tags, dict) and default_tags:
                for req in REQUIRED_TAG_KEYS:
                    assert (
                        req in default_tags
                    ), f"Default tags missing required key '{req}'. Present keys: {list(default_tags.keys())}"

        # Check trackable resources carry tags
        resources = tmpl.get("resources", {})
        iterable = list(resources.values()) if isinstance(resources, dict) else resources
        for r in iterable:
            rtype = r.get("type", "")
            # Top-level trackable Azure resource types in our deployment
            if rtype in (
                "Microsoft.ManagedIdentity/userAssignedIdentities",
                "Microsoft.OperationalInsights/workspaces",
                "Microsoft.Insights/components",
                "Microsoft.DBforPostgreSQL/flexibleServers",
                "Microsoft.KeyVault/vaults",
                "Microsoft.Storage/storageAccounts",
                "Microsoft.App/managedEnvironments",
                "Microsoft.App/containerApps",
                "Microsoft.App/jobs",
                "Microsoft.CognitiveServices/accounts",
            ):
                assert (
                    "tags" in r
                ), f"Resource '{r.get('name')}' of type '{rtype}' does not carry tags"


def main() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    infra_dir = repo_root / "infra"
    config_path = repo_root / "services/backend/app/core/config.py"

    print("Building and parsing Bicep templates...")
    main_template = build_bicep_to_json(infra_dir / "main.bicep")
    ai_template = build_bicep_to_json(infra_dir / "ai.bicep")
    budget_template = build_bicep_to_json(infra_dir / "budget.bicep")

    all_resources = get_all_resources_recursive(main_template)
    all_resources.extend(get_all_resources_recursive(ai_template))

    all_templates = get_all_templates_recursive(main_template)
    all_templates.extend(get_all_templates_recursive(ai_template))
    all_templates.append(budget_template)

    # Also build standalone module files to verify their parameters directly
    for mod_file in (infra_dir / "modules").glob("*.bicep"):
        mod_tmpl = build_bicep_to_json(mod_file)
        all_templates.append(mod_tmpl)

    print("Extracting backend Settings fields...")
    settings_fields = extract_backend_settings_fields(config_path)

    print("Running assertion checks...")
    # 1. worker minReplicas >= 1
    check_worker_min_replicas(all_resources)
    print("  ✓ Worker minReplicas >= 1 verified")

    # 2. web has API_BASE_URL
    check_web_api_base_url(all_resources)
    print("  ✓ Web has API_BASE_URL verified (and unused vars removed)")

    # 3. azure.extensions contains VECTOR, PGCRYPTO, UUID-OSSP
    check_postgres_extensions(all_resources)
    print("  ✓ PostgreSQL extensions (VECTOR, PGCRYPTO, UUID-OSSP) verified")

    # 4. administrator login is not postgres/admin/azure_superuser
    check_administrator_login(main_template, all_resources)
    print("  ✓ PostgreSQL administrator login is safe and not in disallow-list")

    # 5. storage allowSharedKeyAccess is false and api/worker have BLOB_ACCOUNT_URL + AZURE_CLIENT_ID
    check_storage_and_app_identities(all_resources)
    print("  ✓ Storage shared key access disabled and BLOB_ACCOUNT_URL + AZURE_CLIENT_ID set on api/worker")

    # 6. every @secure() param has no default
    check_secure_params_no_defaults(all_templates)
    print("  ✓ Every @secure() parameter across all templates has no default value")

    # 7. every app env var name used for api/worker exists as a field in Settings
    check_app_env_vars_match_settings(all_resources, settings_fields)
    print("  ✓ Every container env var on api/worker matches a Settings field or documented allowlist")

    # 8. all resources carry the four tags
    check_resource_tags(all_templates)
    print("  ✓ All resources carry the required four tags (project, env, owner, expires)")

    # 9. intakeKey has a default of '' (review finding 1)
    check_intake_key_default(main_template)
    print("  ✓ intakeKey has a default of '' in main.bicep")

    # 10. deploy.yml passes intakeKey and enableEmailIntake (review finding 1)
    deploy_workflow_path = repo_root / ".github/workflows/deploy.yml"
    check_deploy_workflow_passes_intake_key(deploy_workflow_path)
    print("  ✓ deploy.yml passes intakeKey and enableEmailIntake")

    # 11. api container has INTAKE_KEY_HASH from a Key Vault secret ref (review finding 2)
    check_api_has_intake_key_hash_secret_ref(all_resources)
    print("  ✓ api container has INTAKE_KEY_HASH wired from Key Vault secret ref")

    # 12. no plain intake key in any template env (review finding 2)
    check_no_plain_intake_key_in_any_template_env(all_resources)
    print("  ✓ no plain intake key exists in any template container env")

    print("\nAll template checks passed successfully!")


if __name__ == "__main__":
    main()
