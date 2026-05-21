# ── Builder stage ──────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build
RUN pip install poetry==2.3.2

COPY pyproject.toml poetry.lock* ./
RUN poetry config virtualenvs.in-project true && \
    poetry install --no-dev --no-interaction --no-ansi

# ── Runtime stage ─────────────────────────────────────────────
FROM python:3.12-slim AS runtime

WORKDIR /app

# Install system dependencies (ffmpeg for media processing)
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*

COPY --from=builder /build/.venv /app/.venv
COPY app/ /app/app/
COPY migrations/ /app/migrations/
COPY alembic.ini /app/

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
