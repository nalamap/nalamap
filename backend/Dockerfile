# ──────────────────────────────────────────────────────────────
# Stage 1 – EXPORT: use Poetry to export a requirements.txt
# ──────────────────────────────────────────────────────────────
# Poetry 2.x can segfault under Podman / QEMU on ARM64 during
# `poetry install`.  We side-step this by only using Poetry to
# *export* a pinned requirements.txt, then let pip do the heavy
# lifting in the build stage.
# ──────────────────────────────────────────────────────────────
FROM python:3.13-slim AS export

ENV POETRY_VERSION=2.1.3 \
    POETRY_HOME=/opt/poetry \
    POETRY_NO_INTERACTION=1

ENV PATH=$POETRY_HOME/bin:$PATH

RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && curl -sSL https://install.python-poetry.org | python3 - --version $POETRY_VERSION \
 && poetry self add poetry-plugin-export \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml poetry.lock ./

RUN poetry export --only main --without-hashes -f requirements.txt -o requirements.txt


# ──────────────────────────────────────────────────────────────
# Stage 2 – BUILD: pip install into a venv using requirements.txt
# ──────────────────────────────────────────────────────────────
FROM python:3.13-slim AS build

# Install every system library needed to *compile* native wheels:
#   build-essential  → gcc / g++ / make (contourpy, etc.)
#   libffi-dev       → cffi
#   python3-dev      → CPython headers
#   libpq-dev        → psycopg
#   libgdal-dev      → pyogrio / GDAL (transitive via geopandas)
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      build-essential \
      libffi-dev \
      python3-dev \
      libpq-dev \
      libgdal-dev \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Create a virtualenv and install deps via pip (no Poetry at runtime)
RUN python -m venv .venv
ENV PATH="/app/.venv/bin:$PATH"

COPY --from=export /app/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt


# ──────────────────────────────────────────────────────────────
# Stage 3 – RUNTIME: slim image with only runtime libraries
# ──────────────────────────────────────────────────────────────
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONOPTIMIZE=1

# No extra system libraries: every native dependency ships its own copy in the
# manylinux wheels (pyogrio.libs -> GDAL, shapely.libs -> GEOS, pyproj.libs ->
# PROJ, psycopg-binary -> libpq). The previously installed libgdal/libgeos/
# libpq5 were never loaded, but dragged in mariadb, poppler, netcdf, hdf5 ...
# and ~230 OS-level findings. `apt-get upgrade` still patches the base layer.
RUN apt-get update \
 && apt-get upgrade -y \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy the pre-built virtualenv from the build stage
COPY --from=build /app/.venv .venv

# pip is not needed at runtime; its vendored setuptools/urllib3/msgpack carry
# CVEs that cannot be updated independently of pip.
RUN python -m pip uninstall -y pip setuptools wheel >/dev/null 2>&1 || true \
 && rm -rf /usr/local/lib/python3.13/site-packages/pip* /usr/local/lib/python3.13/site-packages/setuptools* /usr/local/lib/python3.13/site-packages/pkg_resources* /app/.venv/lib/python3.13/site-packages/pip* /app/.venv/bin/pip*

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
CMD ["/app/.venv/bin/uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
