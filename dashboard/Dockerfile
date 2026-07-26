# Explicitly target amd64 so images built on ARM machines (e.g. Apple Silicon, Windows ARM)
# are always compatible with Cloud Run, which only supports linux/amd64.
FROM --platform=linux/amd64 python:3.12-slim AS builder

WORKDIR /app

# Install build dependencies
RUN pip install --no-cache-dir setuptools>=75.0

# Copy only dependency files first for better caching
COPY pyproject.toml .
COPY src/ src/

# Install the package and dependencies
RUN pip install --no-cache-dir .

FROM --platform=linux/amd64 python:3.12-slim

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application code
COPY src/ src/
COPY docker-entrypoint.sh .

RUN chmod +x docker-entrypoint.sh

# Cloud Run sets PORT env var, default to 8000
ENV PORT=8000

EXPOSE ${PORT}

ENTRYPOINT ["./docker-entrypoint.sh"]
