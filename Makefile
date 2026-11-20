.PHONY: env up down logs migrate seed datagen lint fmt test test-int qa-reindex web-lint web-test web-e2e

SHELL := /bin/bash

ifneq (,$(wildcard .env))
    include .env
    export
endif

env:
	@if [ -f .env ]; then \
		echo ".env already exists, skipping creation."; \
	else \
		python3 -c 'import os, secrets; \
jwt = secrets.token_urlsafe(32); \
demo_pwd = secrets.token_urlsafe(16); \
app_db_pwd = secrets.token_urlsafe(16); \
postgres_pwd = os.environ.get("POSTGRES_PASSWORD", secrets.token_urlsafe(16)); \
db_port = os.environ.get("DB_PORT", "5432"); \
api_port = os.environ.get("API_PORT", "8000"); \
content = f"""APP_ENV=local\nDB_PORT={db_port}\nAPI_PORT={api_port}\nPOSTGRES_USER=postgres\nPOSTGRES_PASSWORD={postgres_pwd}\nAPP_DB_PASSWORD={app_db_pwd}\nDATABASE_URL=postgresql+psycopg://app_user:{app_db_pwd}@localhost:{db_port}/postgres\nDATABASE_URL_MIGRATOR=postgresql+psycopg://postgres:{postgres_pwd}@localhost:{db_port}/postgres\nJWT_SECRET={jwt}\nJWT_ISSUER=brilliant-procurement-ai\nJWT_TTL_MINUTES=60\nDEMO_USER_PASSWORD={demo_pwd}\nBLOB_CONNECTION_STRING=UseDevelopmentStorage=true\nBLOB_CONTAINER=documents\nAI_PROVIDER=replay\nINTEGRATIONS_MODE=mock\n"""; \
open(".env", "w").write(content); \
print("Created .env with random local values."); \
print("=================================================="); \
print(f"Generated DEMO_USER_PASSWORD: {demo_pwd}"); \
print("=================================================="); \
'; \
	fi

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f

migrate:
	cd services/backend && uv run alembic upgrade head

seed:
	cd services/backend && uv run python -m app.core.bootstrap
	@if [ -f seed/load.py ]; then \
		echo "Running seed/load.py..."; \
		cd services/backend && uv run python -m seed.load; \
	fi

qa-reindex:
	cd services/backend && uv run python -m app.qa.reindex

datagen:
	cd services/backend && uv run python -m tools.datagen --replay --check

lint:
	cd services/backend && uv run ruff check . seed tools/datagen && uv run ruff format --check . seed tools/datagen && uv run mypy app seed tools/datagen

fmt:
	cd services/backend && uv run ruff format . seed tools/datagen && uv run ruff check --fix . seed tools/datagen

test:
	cd services/backend && uv run pytest -m "unit or security"

test-int:
	cd services/backend && uv run pytest -m "integration"

web-lint:
	cd apps/web && npm run lint && npm run typecheck

web-test:
	cd apps/web && npm run test

web-e2e:
	cd apps/web && WEB_BASE_URL=$${WEB_BASE_URL:-http://localhost:3000} npm run e2e
