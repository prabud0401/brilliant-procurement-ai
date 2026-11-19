FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates && rm -rf /var/lib/apt/lists/*

COPY services/backend/pyproject.toml services/backend/uv.lock ./

RUN uv sync --frozen --no-install-project

COPY services/backend/app/ ./app/
COPY services/backend/migrations/ ./migrations/
COPY services/backend/alembic.ini ./
COPY seed/ ./seed/
COPY eval/data/replay ./eval/data/replay
COPY tools/ ./tools/

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app"
ENV REPLAY_FIXTURES_DIR="/app/eval/data/replay"

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
