#!/bin/sh
set -e

# Generate a small JS file exposing runtime environment to the client.
# Provide defaults so the browser never falls back to hard-coded localhost values.
RUNTIME_API_BASE_URL="${NEXT_PUBLIC_API_BASE_URL:-/api}"
RUNTIME_API_UPLOAD_URL="${NEXT_PUBLIC_API_UPLOAD_URL:-/api/upload}"
RUNTIME_BACKEND_URL="${NEXT_PUBLIC_BACKEND_URL:-http://backend:8000}"

# Ensure the defaults are also visible to the Next.js process.
export NEXT_PUBLIC_API_BASE_URL="${RUNTIME_API_BASE_URL}"
export NEXT_PUBLIC_API_UPLOAD_URL="${RUNTIME_API_UPLOAD_URL}"
export NEXT_PUBLIC_BACKEND_URL="${RUNTIME_BACKEND_URL}"

# Determine where to write the runtime environment file
# Use RUNTIME_ENV_PATH if set, otherwise fall back to /app/public/runtime-env.js
RUNTIME_ENV_FILE="${RUNTIME_ENV_PATH:-/app/public/runtime-env.js}"

# Ensure the directory exists
mkdir -p "$(dirname "$RUNTIME_ENV_FILE")"

# Create the runtime environment file
cat > "$RUNTIME_ENV_FILE" <<EOF
window.__RUNTIME_CONFIG__ = {
  NEXT_PUBLIC_API_BASE_URL: "${RUNTIME_API_BASE_URL}",
  NEXT_PUBLIC_API_UPLOAD_URL: "${RUNTIME_API_UPLOAD_URL}",
  NEXT_PUBLIC_BACKEND_URL: "${RUNTIME_BACKEND_URL}"
};
EOF

# If we wrote to a custom location, inform about the API route fallback
if [ "$RUNTIME_ENV_FILE" != "/app/public/runtime-env.js" ]; then
  echo "[entrypoint] Runtime config written to: $RUNTIME_ENV_FILE"
  echo "[entrypoint] API route /runtime-env.js will serve the configuration"
fi

# Optional: log for debugging (will show in container logs, safe values only)
echo "[entrypoint] Using runtime environment file: $RUNTIME_ENV_FILE"
echo "[entrypoint] Injected NEXT_PUBLIC_API_BASE_URL=${RUNTIME_API_BASE_URL}"
echo "[entrypoint] Injected NEXT_PUBLIC_API_UPLOAD_URL=${RUNTIME_API_UPLOAD_URL}"
echo "[entrypoint] Injected NEXT_PUBLIC_BACKEND_URL=${RUNTIME_BACKEND_URL}"

exec "$@"
