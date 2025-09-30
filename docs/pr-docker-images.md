# Docker Images for Pull Requests

## Overview

The CI/CD pipeline now builds and pushes Docker images for pull requests, allowing you to test changes without merging to main.

## Image Naming Convention

When you create a pull request, the pipeline will build and push images with the following naming pattern:

```
ghcr.io/geoweaveai/nalamap-frontend:pr-{PR_NUMBER}-{SHORT_SHA}
ghcr.io/geoweaveai/nalamap-backend:pr-{PR_NUMBER}-{SHORT_SHA}
ghcr.io/geoweaveai/nalamap-nginx:pr-{PR_NUMBER}-{SHORT_SHA}
```

For example, if your PR is #123 and the commit SHA starts with `abc1234`, the images would be:
- `ghcr.io/geoweaveai/nalamap-frontend:pr-123-abc1234`
- `ghcr.io/geoweaveai/nalamap-backend:pr-123-abc1234`
- `ghcr.io/geoweaveai/nalamap-nginx:pr-123-abc1234`

## Using PR Images

### Method 1: Update docker-compose.yml temporarily

```yaml
services:
  frontend:
    image: ghcr.io/geoweaveai/nalamap-frontend:pr-123-abc1234
    # remove build section when using pre-built image
  backend:
    image: ghcr.io/geoweaveai/nalamap-backend:pr-123-abc1234
    # remove build section when using pre-built image
  nginx:
    image: ghcr.io/geoweaveai/nalamap-nginx:pr-123-abc1234
    # remove build section when using pre-built image
```

### Method 2: Create a PR-specific docker-compose file

Create `docker-compose.pr.yml`:
```yaml
version: '3.8'
services:
  frontend:
    image: ghcr.io/geoweaveai/nalamap-frontend:pr-123-abc1234
    environment:
      - NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}
      - NEXT_PUBLIC_API_UPLOAD_URL=${NEXT_PUBLIC_API_UPLOAD_URL}
      - RUNTIME_ENV_PATH=/app/runtime-env/runtime-env.js
    ports:
      - "3000:3000"

  backend:
    image: ghcr.io/geoweaveai/nalamap-backend:pr-123-abc1234
    environment:
      - DATABASE_AZURE_URL=${DATABASE_AZURE_URL}
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - AZURE_OPENAI_ENDPOINT=${AZURE_OPENAI_ENDPOINT}
      - AZURE_OPENAI_API_KEY=${AZURE_OPENAI_API_KEY}
      - AZURE_OPENAI_DEPLOYMENT=${AZURE_OPENAI_DEPLOYMENT}
      - AZURE_OPENAI_API_VERSION=${AZURE_OPENAI_API_VERSION}
      - LLM_PROVIDER=${LLM_PROVIDER}
    ports:
      - "8000:8000"

  nginx:
    image: ghcr.io/geoweaveai/nalamap-nginx:pr-123-abc1234
    environment:
      - BACKEND_PROTOCOL=http
      - BACKEND_URL=backend:8000
      - FRONTEND_PROTOCOL=http
      - FRONTEND_URL=frontend:3000
    ports:
      - "80:80"
    depends_on:
      - frontend
      - backend
```

Then run: `docker-compose -f docker-compose.pr.yml up -d`

### Method 3: Use Docker CLI directly

```bash
# Pull the images
docker pull ghcr.io/geoweaveai/nalamap-frontend:pr-123-abc1234
docker pull ghcr.io/geoweaveai/nalamap-backend:pr-123-abc1234
docker pull ghcr.io/geoweaveai/nalamap-nginx:pr-123-abc1234

# Run containers
docker run -d --name test-frontend -p 3000:3000 ghcr.io/geoweaveai/nalamap-frontend:pr-123-abc1234
docker run -d --name test-backend -p 8000:8000 ghcr.io/geoweaveai/nalamap-backend:pr-123-abc1234
docker run -d --name test-nginx -p 80:80 ghcr.io/geoweaveai/nalamap-nginx:pr-123-abc1234
```

## Finding Your Image Tags

1. Go to your pull request on GitHub
2. Click on the "Checks" tab
3. Look for the "Build and push Docker images" workflow
4. Check the "Show generated tags" step output to see the exact tags

Or check the packages section of your GitHub repository:
`https://github.com/geoweaveai/geoweaver/packages`

## Authentication

To pull private images, you'll need to authenticate with GitHub Container Registry:

```bash
echo $GITHUB_TOKEN | docker login ghcr.io -u $GITHUB_USERNAME --password-stdin
```

Where `$GITHUB_TOKEN` is a personal access token with `read:packages` permission.

## Cleanup

PR images are automatically tagged and won't interfere with production images. They can be manually deleted from the GitHub packages interface if needed.