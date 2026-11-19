.PHONY: env up down logs migrate seed lint fmt test test-int

SHELL := /bin/bash

env:
	@if [ -f .env ]; then \
		echo ".env already exists, skipping creation."; \
	else \
		python3 -c 'import secrets; \
jwt = secrets.token_urlsafe(32); \
pwd = secrets.token_urlsafe(16); \
content = f"""APP_ENV=local\nDATABASE_URL=postgresql+psycopg://app_user:app_user@localhost:5432/postgres\nDATABASE_URL_MIGRATOR=postgresql+psycopg://postgres:postgres@localhost:5432/postgres\nJWT_SECRET={jwt}\nJWT_ISSUER=brilliant-procurement-ai\nJWT_TTL_MINUTES=60\nDEMO_USER_PASSWORD={pwd}\nBLOB_CONNECTION_STRING=UseDevelopmentStorage=true\nBLOB_CONTAINER=documents\nAI_PROVIDER=mock\nINTEGRATIONS_MODE=mock\n"""; \
open(".env", "w").write(content); \
print("Created .env with random local values."); \
print("=================================================="); \
print(f"Generated DEMO_USER_PASSWORD: {pwd}"); \
print("=================================================="); \
'; \
	fi

up:
	docker compose up -d

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

lint:
	cd services/backend && uv run ruff check . && uv run ruff format --check . && uv run mypy app

fmt:
	cd services/backend && uv run ruff format . && uv run ruff check --fix .

test:
	cd services/backend && uv run pytest -m "unit or security"

test-int:
	cd services/backend && uv run pytest -m "integration"
