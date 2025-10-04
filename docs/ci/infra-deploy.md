# Cross-repo deploy via repository_dispatch

This repository builds and pushes Docker images for frontend, backend, and nginx, then dispatches a deployment event to `nalamap/cloud-infrastructure` with the image tags and digests.

## Triggers

- push to default branch (main)
- push of version tags matching `v*.*.*`
- pull_request (as deploy-preview, for testing)

## Secrets required

- `CLOUD_INFRA_REPO_TOKEN`: GitHub Personal Access Token with `repo` scope that can access `nalamap/cloud-infrastructure`.
  - Store as a Repository Secret in this repo.
  - Used only in the dispatch step to call the GitHub API for the target repo.

## Payload format

Event types:
- `deploy` for main and tags
- `deploy-preview` for pull requests

client_payload fields:
- `source_repository`: "owner/repo" of this repo
- `ref`: full ref (e.g., `refs/heads/main`, `refs/tags/v1.2.3`)
- `sha`: commit SHA
- `run_id`, `run_attempt`: numbers to link back to the workflow run
- `pull_request`: PR number for preview events, null otherwise
- `images`: array of objects for each built image
  - `name`: matrix name (frontend|backend|nginx)
  - `image`: base image name (e.g., `ghcr.io/<owner>/nalamap-frontend`)
  - `digest`: content digest from the Docker build
  - `tags`: list of pushed tags (full `ghcr.io/...:tag` strings)

## Example receiver workflow (in cloud-infrastructure)

```yaml
name: Deploy
on:
  repository_dispatch:
    types: [deploy, deploy-preview]

jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - name: Inspect payload
        run: |
          echo "Event: ${{ github.event.action || github.event.client_payload != '' && github.event.action || 'n/a' }}"
          echo "Type: ${{ github.event.action }}"
          echo "Payload:" | cat
          echo '${{ toJson(github.event.client_payload) }}'

      # TODO: Use github.event.client_payload.images[*].image and .digest
      # to update manifests or Helm values and perform deployment.
```

Notes:
- The digest corresponds to the pushed image content; you can safely use `image@digest` for immutable deployments.
- Tags are provided for convenience (branch, PR, semver, sha, and latest on main/tags).
