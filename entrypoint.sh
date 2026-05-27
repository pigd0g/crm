#!/bin/sh
set -e
set -u

if ! python manage.py migrate --noinput; then
    echo >&2 ""
    echo >&2 "Startup failed while applying migrations."
    echo >&2 "Check that DATABASE_URL points to an existing PostgreSQL database."
    echo >&2 "The container can run migrations, but it does not create the database itself."
    exit 1
fi

python manage.py collectstatic --noinput

exec gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000}
