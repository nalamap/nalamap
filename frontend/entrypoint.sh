#!/bin/sh
set -e

# Generate a small JS file exposing runtime environment to the client.
cat > /app/public/runtime-env.js <<EOF
window.__RUNTIME_CONFIG__ = {
  NEXT_PUBLIC_API_BASE_URL: "${NEXT_PUBLIC_API_BASE_URL}",
  NEXT_PUBLIC_BACKEND_URL: "${NEXT_PUBLIC_BACKEND_URL}"
};
EOF

# Optional: log for debugging (will show in container logs, safe values only)
echo "[entrypoint] Injected NEXT_PUBLIC_API_BASE_URL=${NEXT_PUBLIC_API_BASE_URL}"
echo "[entrypoint] Injected NEXT_PUBLIC_BACKEND_URL=${NEXT_PUBLIC_BACKEND_URL}"

exec "$@"
