FROM python:3.12.11-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app/src
WORKDIR /app
RUN useradd --create-home --uid 10001 appuser
COPY pyproject.toml uv.lock alembic.ini ./
COPY src ./src
COPY migrations ./migrations
COPY scripts ./scripts
RUN pip install --no-cache-dir uv==0.8.15 && uv sync --locked --no-dev
USER appuser
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "travel_agent.local_dev:app", "--host", "0.0.0.0", "--port", "8000", "--no-server-header"]
