# Imagen de runtime de IncidentOps (ADR-004): python:3.12-slim + uv con dependencias bloqueadas.
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.3 /uv /uvx /bin/

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Capa de dependencias (se reutiliza mientras pyproject.toml/uv.lock no cambien).
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Código de la aplicación.
COPY data ./data
COPY src ./src

EXPOSE 8000
CMD ["uvicorn", "src.adapters.inbound.api.app:app", "--host", "0.0.0.0", "--port", "8000"]
