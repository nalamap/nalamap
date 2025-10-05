#!/bin/sh
# Be resilient: don't exit on non-critical errors (like writing runtime config)
set -u

# Generate a small JS file exposing runtime environment to the client.
# Provide defaults so the browser never falls back to hard-coded localhost values.
RUNTIME_API_BASE_URL="${NEXT_PUBLIC_API_BASE_URL:-/api}"
RUNTIME_API_UPLOAD_URL="${NEXT_PUBLIC_API_UPLOAD_URL:-/api/upload}"
RUNTIME_BACKEND_URL="${NEXT_PUBLIC_BACKEND_URL:-http://backend:8000}"

# Ensure the defaults are also visible to the Next.js process.
export NEXT_PUBLIC_API_BASE_URL="${RUNTIME_API_BASE_URL}"
export NEXT_PUBLIC_API_UPLOAD_URL="${RUNTIME_API_UPLOAD_URL}"
export NEXT_PUBLIC_BACKEND_URL="${RUNTIME_BACKEND_URL}"

"${RUNTIME_ENV_PATH:=}" >/dev/null 2>&1 || true
# Determine where to write the runtime environment file
# Prefer provided RUNTIME_ENV_PATH; otherwise default to /app/public/runtime-env.js
RUNTIME_ENV_FILE="${RUNTIME_ENV_PATH:-/app/public/runtime-env.js}"

# Try to ensure the directory exists; if not writable, fall back to /tmp
TARGET_DIR="$(dirname "$RUNTIME_ENV_FILE")"
if ! mkdir -p "$TARGET_DIR" 2>/dev/null; then
  echo "[entrypoint] WARN: Cannot create $TARGET_DIR (permission denied). Falling back to /tmp"
  RUNTIME_ENV_FILE="/tmp/runtime-env.js"
  export RUNTIME_ENV_PATH="$RUNTIME_ENV_FILE"
  mkdir -p "/tmp" 2>/dev/null || true
fi

# Attempt to create the runtime environment file; on failure, continue (route will fall back)
if ! cat > "$RUNTIME_ENV_FILE" <<EOF
window.__RUNTIME_CONFIG__ = {
  NEXT_PUBLIC_API_BASE_URL: "${RUNTIME_API_BASE_URL}",
  NEXT_PUBLIC_API_UPLOAD_URL: "${RUNTIME_API_UPLOAD_URL}",
  NEXT_PUBLIC_BACKEND_URL: "${RUNTIME_BACKEND_URL}"
};
EOF
then
  echo "[entrypoint] WARN: Failed to write runtime config to $RUNTIME_ENV_FILE. The /runtime-env.js route will serve a fallback from environment variables."
else
  echo "[entrypoint] Runtime config written to: $RUNTIME_ENV_FILE"
fi

# Optional: log for debugging (will show in container logs, safe values only)
echo "[entrypoint] Using runtime environment file: $RUNTIME_ENV_FILE"
echo "[entrypoint] Injected NEXT_PUBLIC_API_BASE_URL=${RUNTIME_API_BASE_URL}"
echo "[entrypoint] Injected NEXT_PUBLIC_API_UPLOAD_URL=${RUNTIME_API_UPLOAD_URL}"
echo "[entrypoint] Injected NEXT_PUBLIC_BACKEND_URL=${RUNTIME_BACKEND_URL}"

exec "$@"
