#!/bin/sh
set -e

echo "Running database migrations..."
alembic upgrade head

echo "Starting ApplyBot dashboard on port ${PORT:-8000}..."
exec applybot serve --host 0.0.0.0 --port "${PORT:-8000}"
