#!/usr/bin/env sh
set -eu

echo "=== Running database migrations ==="
python manage.py migrate --noinput

echo "=== Starting Daphne ASGI server on port ${PORT:-8000} ==="
exec daphne -b 0.0.0.0 -p "${PORT:-8000}" config.asgi:application