#!/usr/bin/env sh
set -e

# Run DB migrations on startup (safe to run multiple times)
python manage.py migrate --noinput

# Collect static at runtime in case build pipeline skipped it
python manage.py collectstatic --noinput

# Start the app
exec gunicorn scheduler.wsgi:application --bind 0.0.0.0:${PORT:-8000}
