FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY app ./app

# Free hosts have an ephemeral disk; the app reseeds demo data on boot.
ENV PATH="/app/.venv/bin:$PATH" DB_PATH=/tmp/data.db CHECKPOINT_DB=/tmp/checkpoints.db
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
