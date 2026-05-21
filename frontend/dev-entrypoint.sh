#!/bin/sh
set -eu

APP_DIR="/app"
CACHE_DIR="/opt/node_modules"
MANIFEST_DIR="/opt/deps-manifest"
MARKER_FILE="$APP_DIR/node_modules/.nalamap-deps-hash"

detect_lockfile() {
  for candidate in yarn.lock package-lock.json pnpm-lock.yaml; do
    if [ -f "$APP_DIR/$candidate" ]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done

  printf '%s\n' "package.json"
}

lock_hash() {
  sha256sum "$1" | cut -d ' ' -f1
}

install_dependencies() {
  case "$LOCKFILE_NAME" in
    yarn.lock)
      yarn --frozen-lockfile
      ;;
    pnpm-lock.yaml)
      corepack enable pnpm
      pnpm install --frozen-lockfile
      ;;
    package-lock.json)
      npm ci
      ;;
    *)
      npm install
      ;;
  esac
}

start_dev_server() {
  case "$LOCKFILE_NAME" in
    yarn.lock)
      exec yarn dev
      ;;
    pnpm-lock.yaml)
      corepack enable pnpm
      exec pnpm dev
      ;;
    *)
      exec npm run dev
      ;;
  esac
}

LOCKFILE_NAME="$(detect_lockfile)"
LOCKFILE_PATH="$APP_DIR/$LOCKFILE_NAME"
IMAGE_LOCKFILE_PATH="$MANIFEST_DIR/$LOCKFILE_NAME"
CURRENT_HASH="$(lock_hash "$LOCKFILE_PATH")"

NEEDS_INSTALL="true"
if [ -x "$APP_DIR/node_modules/.bin/next" ] && [ -f "$MARKER_FILE" ] && [ "$(cat "$MARKER_FILE")" = "$CURRENT_HASH" ]; then
  NEEDS_INSTALL="false"
fi

if [ "$NEEDS_INSTALL" = "true" ]; then
  mkdir -p "$APP_DIR/node_modules"
  find "$APP_DIR/node_modules" -mindepth 1 -maxdepth 1 -exec rm -rf {} +

  if [ -d "$CACHE_DIR" ] && [ -f "$IMAGE_LOCKFILE_PATH" ] && [ "$(lock_hash "$IMAGE_LOCKFILE_PATH")" = "$CURRENT_HASH" ]; then
    echo "[dev-entrypoint] Restoring dependencies from image cache"
    cp -a "$CACHE_DIR"/. "$APP_DIR/node_modules/"
  else
    echo "[dev-entrypoint] Installing dependencies for $LOCKFILE_NAME"
    install_dependencies
  fi

  printf '%s\n' "$CURRENT_HASH" > "$MARKER_FILE"
fi

start_dev_server
