# Database & Migrations Guide

**Last Updated**: October 14, 2025

This guide walks through setting up a PostGIS database and using Alembic to manage schema migrations
for the NaLaMap backend, which uses async SQLAlchemy ORM models.

---

## 📋 Table of Contents

1. [Prerequisites](#prerequisites)
2. [Configure Environment Variables](#configure-environment-variables)
3. [Install Dependencies](#install-dependencies)
4. [Initialize Alembic](#initialize-alembic)
5. [Configure Alembic](#configure-alembic)
6. [Generate Migrations](#generate-migrations)
7. [Apply Migrations](#apply-migrations)
8. [Tips & Troubleshooting](#tips--troubleshooting)

---

## Overview

NaLaMap backend defines its data models (e.g. `User`) via SQLAlchemy ORM and stores data in a PostGIS-enabled PostgreSQL database.
Alembic provides a lightweight way to generate and apply schema migrations based on these ORM models.

## Prerequisites

- PostgreSQL with PostGIS extension installed and running.
- `DATABASE_AZURE_URL` (or `DATABASE_URL`) environment variable pointing to your PostGIS database.
- Backend dependencies installed via Poetry.

## Configure Environment Variables

Ensure your `.env` (or environment) contains a database URL:

```ini
# PostGIS-enabled database for local development
DATABASE_URL=postgis://<user>:<password>@<host>:5432/<database>
# Or for Azure PostgreSQL
DATABASE_AZURE_URL=postgresql://<user>@<host>.postgres.database.azure.com:5432/<database>
```

## Install Dependencies

From the `backend/` directory:

```bash
# Install common dependencies + Alembic for migrations
poetry install

# Ensure Alembic is available
poetry add --group dev alembic
```

## Initialize Alembic

Run the Alembic init command to scaffold migration scripts:

```bash
cd backend
poetry run alembic init alembic
```

This creates:

- `alembic.ini` (config file)
- `alembic/` directory with `env.py` and `versions/` folder

## Configure Alembic

1. **Edit `alembic.ini`** – set the database URL under `[alembic:runtime]`:

   ```ini
   [alembic]
   script_location = alembic

   [alembic:runtime]
   sqlalchemy.url = postgis://<user>:<password>@<host>:5432/<database>
   ```

2. **Update `alembic/env.py`** to import your ORM metadata and use an async engine.
   Refer to the example in `backend/alembic/env.py` for the full async setup.

## Generate Migrations

Whenever your ORM models change, auto‑generate a new revision:

```bash
cd backend
poetry run alembic revision --autogenerate -m "describe your change"
```

This will create a timestamped file under `backend/alembic/versions/` containing the DDL
needed to bring your database schema in sync with your models.

## Apply Migrations

To apply all pending migrations to the database:

```bash
cd backend
poetry run alembic upgrade head
```

You can also target specific revisions or downgrade:

```bash
# Upgrade to a specific revision
poetry run alembic upgrade <revision_id>

# Downgrade one step
poetry run alembic downgrade -1
```

## Tips & Troubleshooting

- **Environment URL mismatch**: Ensure the `sqlalchemy.url` in `alembic.ini`
  matches your env var or local connection.
- **Autogenerate skips changes**: If Alembic doesn’t detect changes,
  verify models are imported in `env.py` and `target_metadata` is set.
- **Rebuild migrations**: To reset migrations (dev only), you can
  delete the `alembic/versions/*` files and re-run `alembic revision --autogenerate`.
- **CI integration**: In CI/CD, run `alembic upgrade head` against a test database to
  ensure migrations remain idempotent.

---

_This guide is part of the NaLaMap documentation suite._
