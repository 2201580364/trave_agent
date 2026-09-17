FROM ghcr.io/astral-sh/uv:0.8.15 AS uv-bin

FROM python:3.12.11-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/src PATH=/app/.venv/bin:$PATH
WORKDIR /app
RUN useradd --create-home --uid 10001 appuser
COPY pyproject.toml uv.lock alembic.ini ./
COPY src ./src
COPY migrations ./migrations
COPY scripts ./scripts
COPY data/governance ./data/governance
COPY --from=uv-bin /uv /uvx /bin/
RUN uv sync --frozen --no-dev
RUN mkdir -p /app/var/ops /app/logs && chown -R appuser:appuser /app/var /app/logs
USER appuser
EXPOSE 8000
CMD ["python", "scripts/run_published_app.py", "--host", "0.0.0.0", "--port", "8000"]
