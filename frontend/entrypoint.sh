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

cat > /app/public/runtime-env.js <<EOF
window.__RUNTIME_CONFIG__ = {
  NEXT_PUBLIC_API_BASE_URL: "${RUNTIME_API_BASE_URL}",
  NEXT_PUBLIC_API_UPLOAD_URL: "${RUNTIME_API_UPLOAD_URL}",
  NEXT_PUBLIC_BACKEND_URL: "${RUNTIME_BACKEND_URL}"
};
EOF

# Optional: log for debugging (will show in container logs, safe values only)
echo "[entrypoint] Injected NEXT_PUBLIC_API_BASE_URL=${RUNTIME_API_BASE_URL}"
echo "[entrypoint] Injected NEXT_PUBLIC_API_UPLOAD_URL=${RUNTIME_API_UPLOAD_URL}"
echo "[entrypoint] Injected NEXT_PUBLIC_BACKEND_URL=${RUNTIME_BACKEND_URL}"

exec "$@"
