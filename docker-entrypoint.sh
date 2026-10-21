#!/bin/sh
set -eu
if [ "${1:-}" = "web" ]; then
    python manage.py migrate --noinput
    python manage.py collectstatic --noinput
    exec gunicorn it.wsgi:application --bind 0.0.0.0:8000 --workers 2 --timeout 120
fi
if [ "${1:-}" = "worker" ]; then
    exec python manage.py run_backup_worker
fi
exec "$@"
