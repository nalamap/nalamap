# ──────────────────────────────────────────────────────────────
# Stage 1 – BUILD: install Poetry + all Python deps in a venv
# ──────────────────────────────────────────────────────────────
FROM python:3.14-slim AS build

ENV POETRY_VERSION=1.8.0 \
    POETRY_HOME=/opt/poetry \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_NO_INTERACTION=1

ENV PATH=$POETRY_HOME/bin:$PATH

# Install every system library needed to *compile* native wheels:
#   build-essential  → gcc / g++ / make (contourpy, etc.)
#   libffi-dev       → cffi
#   python3-dev      → CPython headers
#   libpq-dev        → psycopg
#   libgdal-dev      → pyogrio / GDAL (transitive via geopandas)
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      curl \
      build-essential \
      libffi-dev \
      python3-dev \
      libpq-dev \
      libgdal-dev \
 && curl -sSL https://install.python-poetry.org | python3 - --version $POETRY_VERSION \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy lock files first → layer is cached until deps change
COPY pyproject.toml poetry.lock ./

# Install production deps into .venv inside /app
RUN poetry install --only main --no-root


# ──────────────────────────────────────────────────────────────
# Stage 2 – RUNTIME: slim image with only runtime libraries
# ──────────────────────────────────────────────────────────────
FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONOPTIMIZE=1

# Runtime system libraries only (no compilers):
#   libpq5           → psycopg runtime
#   libgdal36t64     → pyogrio / GDAL runtime (Debian trixie package name)
#   libgeos-dev      → shapely runtime
# Note: The exact libgdal package name may vary by Debian version.
# We use a glob install to handle version differences.
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      libpq5 \
      libgeos-dev \
 && apt-get install -y --no-install-recommends libgdal36t64 \
    || apt-get install -y --no-install-recommends $(apt-cache search --names-only '^libgdal[0-9]' | head -1 | cut -d' ' -f1) \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy the pre-built virtualenv from the build stage
COPY --from=build /app/.venv .venv

# Put the venv's Python on PATH
ENV PATH="/app/.venv/bin:$PATH"

# Copy application code
COPY . .

# Precompile Python bytecode for faster imports at runtime
RUN python -m compileall -q .

# Thread pool defaults (overridable at runtime)
ENV NALAMAP_HIGH_PRIORITY_THREADS="" \
    NALAMAP_LOW_PRIORITY_THREADS="" \
    NALAMAP_MAX_CONCURRENT_PRELOADS="3"

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
