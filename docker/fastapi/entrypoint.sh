#!/bin/bash
set -e
echo "Running migrations..."
alembic upgrade head
echo "Starting FastAPI..."
exec gunicorn backend.main:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
