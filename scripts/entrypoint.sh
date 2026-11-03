#!/bin/sh
set -e

echo "=== Starting container entrypoint ==="

# Wait for DB and Redis to be ready
echo "Checking service dependencies..."
python scripts/wait_for_services.py

# Run Alembic Database Migrations
echo "Applying database migrations..."
alembic upgrade head

echo "Database migrations completed successfully."

# Execute the application command passed in Dockerfile CMD or docker-compose
echo "Starting application server..."
exec "$@"

