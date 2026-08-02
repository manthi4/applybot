# Explicitly target amd64 so images built on ARM machines (e.g. Apple Silicon, Windows ARM)
# are always compatible with Cloud Run, which only supports linux/amd64.
FROM --platform=linux/amd64 python:3.12-slim AS builder

WORKDIR /app

# Copy only dependency files first for better caching. setuptools>=75.0 is pulled
# in automatically by pip's build isolation (declared in pyproject.toml [build-system]).
COPY pyproject.toml .

# Copy only the applybot subpackages the dashboard actually imports. The dashboard
# is NOT self-contained — it imports models, application, storage, tracking, llm,
# and profile (transitively, via application.resume_tailor). Omitted on purpose:
#   - discovery/  — invoked over HTTP (services/discovery.py), never imported
#   - cli.py      — entrypoint below runs the dashboard module directly
# `setuptools.packages.find` (where=["src"]) discovers only the packages present,
# so a partial src/ tree installs cleanly.
COPY src/applybot/__init__.py src/applybot/config.py src/applybot/storage.py src/applybot/
COPY src/applybot/models src/applybot/models
COPY src/applybot/llm src/applybot/llm
COPY src/applybot/profile src/applybot/profile
COPY src/applybot/application src/applybot/application
COPY src/applybot/tracking src/applybot/tracking
COPY src/applybot/dashboard src/applybot/dashboard

# Install the package and dependencies
RUN pip install --no-cache-dir .

FROM --platform=linux/amd64 python:3.12-slim

WORKDIR /app

# Copy installed packages (including the applybot package itself) from builder.
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Lean runtime: unbuffered stdout/stderr for Cloud Run logging, no .pyc files.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000 \
    HOST=0.0.0.0

EXPOSE ${PORT}

# Run as a non-root user for least privilege.
RUN useradd --create-home --uid 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Run the dashboard module directly — no dependency on the top-level
# `applybot` CLI (src/applybot/cli.py), which lives outside this module.
ENTRYPOINT ["python", "-m", "applybot.dashboard.frontend"]
