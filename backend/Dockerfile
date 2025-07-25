# 1. Build stage: use Poetry to export requirements.txt
FROM python:3.13-slim AS build

# 1a. Define Poetry version and install location
ENV POETRY_VERSION=1.8.0
ENV POETRY_HOME=/opt/poetry

# 1b. Add Poetry to PATH
ENV PATH=$POETRY_HOME/bin:$PATH
# Install system deps for Poetry & Python builds, then install Poetry
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      curl \
      build-essential \
      libffi-dev \
      python3-dev \
 && curl -sSL https://install.python-poetry.org | python3 - --version $POETRY_VERSION \
 && pip install --upgrade pip \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy only lock files to leverage cache
COPY pyproject.toml poetry.lock ./

# Export locked deps to a flat requirements.txt
RUN poetry export \
      --format=requirements.txt \
      --without-hashes \
      --output=requirements.txt


# 2. Final stage: install only production dependencies
FROM python:3.13-slim

# Environment settings
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install OS‐level deps (e.g. for psycopg3)
RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      gcc \
      libpq-dev \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy in the exported requirements from build stage
COPY --from=build /app/requirements.txt .

# Install Python dependencies
RUN pip install --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

# Copy the rest of the app code
COPY . .

# Expose the port and set the default command
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
