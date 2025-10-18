#!/bin/bash

# ==============================================================================
# Quick Startup Check Script
# ==============================================================================
# This script provides a quick check of container startup times
# Usage: ./quick-startup-check.sh
# ==============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Service URLs
NGINX_HEALTH="http://localhost:80/health/nginx"
BACKEND_HEALTH="http://localhost:80/health/backend"
FRONTEND_HEALTH="http://localhost:80/health/frontend"

log() {
    echo -e "${BLUE}[$(date +%H:%M:%S.%3N)]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[$(date +%H:%M:%S.%3N)]${NC} ✓ $1"
}

log_error() {
    echo -e "${RED}[$(date +%H:%M:%S.%3N)]${NC} ✗ $1"
}

log_highlight() {
    echo -e "${CYAN}[$(date +%H:%M:%S.%3N)]${NC} $1"
}

# Check if a service responds
check_service() {
    local url=$1
    local name=$2
    local max_wait=${3:-120}
    local start_time=$(date +%s.%N)
    
    while true; do
        if curl -sf "$url" > /dev/null 2>&1; then
            local end_time=$(date +%s.%N)
            local duration=$(echo "$end_time - $start_time" | bc)
            log_success "$name ready in ${duration}s"
            return 0
        fi
        
        local current_time=$(date +%s.%N)
        local elapsed=$(echo "$current_time - $start_time" | bc)
        
        if (( $(echo "$elapsed > $max_wait" | bc -l) )); then
            log_error "$name failed to respond within ${max_wait}s"
            return 1
        fi
        
        sleep 0.5
    done
}

echo ""
log_highlight "================================================"
log_highlight "  NaLaMap Container Startup Check"
log_highlight "================================================"
echo ""

# Cleanup first
log "Stopping any running containers..."
docker-compose down 2>/dev/null || true
sleep 2

# Start timing
OVERALL_START=$(date +%s.%N)

log "Starting docker-compose up -d..."
COMPOSE_START=$(date +%s.%N)
docker-compose up -d 2>&1 | grep -v "Container" | tail -n 5
COMPOSE_END=$(date +%s.%N)
COMPOSE_TIME=$(echo "$COMPOSE_END - $COMPOSE_START" | bc)
log_success "Docker-compose up completed in ${COMPOSE_TIME}s"
echo ""

log "Waiting for services to become healthy..."
echo ""

# Check services
check_service "$NGINX_HEALTH" "Nginx" 60
check_service "$BACKEND_HEALTH" "Backend" 120
check_service "$FRONTEND_HEALTH" "Frontend" 120

OVERALL_END=$(date +%s.%N)
OVERALL_TIME=$(echo "$OVERALL_END - $OVERALL_START" | bc)

echo ""
log_highlight "================================================"
log_highlight "  All services ready in ${OVERALL_TIME}s"
log_highlight "================================================"
echo ""

log "Testing end-to-end request..."
if curl -sf "http://localhost:80/" > /dev/null 2>&1; then
    log_success "End-to-end request successful"
else
    log_error "End-to-end request failed"
fi

echo ""
log_highlight "Container status:"
docker-compose ps
echo ""
