FROM python:3.12-slim

# Copy the lightweight uv binary from Astral's official image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Environment configuration:
# - UV_SYSTEM_PYTHON=1: Tells uv to install into standard system Python (no venv needed in single-stage)
# - UV_COMPILE_BYTECODE=1: Pre-compiles .pyc files for faster Cloud Run container startup times
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_SYSTEM_PYTHON=1 \
    UV_COMPILE_BYTECODE=1 \
    PORT=8000 \
    HOST=0.0.0.0

EXPOSE ${PORT}

# 1. Copy project metadata first for layer caching
COPY pyproject.toml .

# 2. Dummy package setup + BuildKit cache mount
# The cache mount keeps downloaded wheel files on the host machine across rebuilds
RUN mkdir -p src/applybot && touch src/applybot/__init__.py
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install .

# 3. Copy actual application source code
COPY src/applybot/__init__.py src/applybot/config.py src/applybot/storage.py src/applybot/
COPY src/applybot/models src/applybot/models
COPY src/applybot/llm src/applybot/llm
COPY src/applybot/profile src/applybot/profile
COPY src/applybot/application src/applybot/application
COPY src/applybot/dashboard src/applybot/dashboard

# 4. Install local package without re-downloading dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install --no-deps .

# 5. Non-root user for Cloud Run security best practices
RUN useradd --create-home --uid 1000 appuser && chown -R appuser:appuser /app
USER appuser

ENTRYPOINT ["python", "-m", "applybot.dashboard.frontend"]