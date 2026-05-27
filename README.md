# Sales CRM

A simple Django-based sales CRM with:

- a kanban pipeline and table/list deal views
- multiple contacts per deal
- deal-level notes and history
- an external Postgres database configured through `.env`
- a single Docker container for the application

## Environment

Copy `.env.example` to `.env` and update `DATABASE_URL` to point at your existing Postgres server.

The database in `DATABASE_URL` must already exist. The container runs Django migrations on startup, but it does not create the PostgreSQL database itself.

If your server is reachable but the container exits on startup, the most common cause is that the database name in `DATABASE_URL` does not exist yet.

## Run locally

```powershell
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

## Run with Docker

```powershell
docker build -t sales-crm .
docker run --env-file .env -p 8000:8000 sales-crm
docker run -d --name sales-crm --env-file .env -p 8000:8000 sales-crm
```

The container runs migrations and collects static assets on startup before serving the app with Gunicorn.
Its system timezone is set to `Australia/Melbourne`.
