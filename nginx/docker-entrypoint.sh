#!/bin/sh
# Substitute environment variables in the Nginx config template and output the final config
# Provide sensible defaults so the container does not fall back to Nginx defaults when
# variables are missing.
: "${BACKEND_PROTOCOL:=http}"
: "${BACKEND_URL:=backend:8000}"
: "${FRONTEND_PROTOCOL:=http}"
: "${FRONTEND_URL:=frontend:3000}"

echo "[entrypoint] Using BACKEND_PROTOCOL=${BACKEND_PROTOCOL}"
echo "[entrypoint] Using BACKEND_URL=${BACKEND_URL}"
echo "[entrypoint] Using FRONTEND_PROTOCOL=${FRONTEND_PROTOCOL}"
echo "[entrypoint] Using FRONTEND_URL=${FRONTEND_URL}"

envsubst '$BACKEND_PROTOCOL $BACKEND_URL $FRONTEND_PROTOCOL $FRONTEND_URL' < /etc/nginx/nginx.conf.envsubst > /etc/nginx/nginx.conf

# Execute the command passed to the entrypoint (nginx)
exec "$@"
