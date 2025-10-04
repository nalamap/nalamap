#!/bin/sh
# Substitute environment variables in the Nginx config template and output the final config
# Provide sensible defaults so the container does not fall back to Nginx defaults when
# variables are missing.
: "${BACKEND_PROTOCOL:=http}"
: "${BACKEND_URL:=backend:8000}"
: "${FRONTEND_PROTOCOL:=http}"
: "${FRONTEND_URL:=frontend:3000}"
# Default DNS resolver: prioritize Docker internal DNS 127.0.0.11; allow override; fallback to Azure DNS if set by user
: "${DNS_RESOLVER:=127.0.0.11}"
# Azure Blob Storage domain for CORS (empty by default, set when using Azure Blob Storage)
: "${AZURE_BLOB_DOMAIN:=}"

echo "[entrypoint] Using BACKEND_PROTOCOL=${BACKEND_PROTOCOL}"
echo "[entrypoint] Using BACKEND_URL=${BACKEND_URL}"
echo "[entrypoint] Using FRONTEND_PROTOCOL=${FRONTEND_PROTOCOL}"
echo "[entrypoint] Using FRONTEND_URL=${FRONTEND_URL}"
echo "[entrypoint] Using DNS_RESOLVER=${DNS_RESOLVER}"
echo "[entrypoint] Using AZURE_BLOB_DOMAIN=${AZURE_BLOB_DOMAIN}"

envsubst '$BACKEND_PROTOCOL $BACKEND_URL $FRONTEND_PROTOCOL $FRONTEND_URL $DNS_RESOLVER $AZURE_BLOB_DOMAIN' < /etc/nginx/nginx.conf.envsubst > /etc/nginx/nginx.conf

# Execute the command passed to the entrypoint (nginx)
exec "$@"
