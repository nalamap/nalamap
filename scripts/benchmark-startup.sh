#!/bin/bash

# ==============================================================================
# Container Startup Benchmark Script
# ==============================================================================
# This script measures cold start times for all containers when scaling from zero
# Usage: ./benchmark-startup.sh [iterations]
# Example: ./benchmark-startup.sh 3
# ==============================================================================

set -e

# Configuration
ITERATIONS=${1:-5}
RESULTS_DIR="./benchmark-results"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
RESULTS_FILE="${RESULTS_DIR}/startup_benchmark_${TIMESTAMP}.json"
LOG_FILE="${RESULTS_DIR}/startup_benchmark_${TIMESTAMP}.log"

# Service URLs
NGINX_URL="http://localhost:80"
BACKEND_URL="http://localhost:8000"
FRONTEND_URL="http://localhost:3000"

# Health check endpoints
NGINX_HEALTH="${NGINX_URL}/health/nginx"
BACKEND_HEALTH="${NGINX_URL}/health/backend"
FRONTEND_HEALTH="${NGINX_URL}/health/frontend"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ==============================================================================
# Functions
# ==============================================================================

log() {
    echo -e "${BLUE}[$(date +%H:%M:%S)]${NC} $1" | tee -a "$LOG_FILE"
}

log_success() {
    echo -e "${GREEN}[$(date +%H:%M:%S)]${NC} ✓ $1" | tee -a "$LOG_FILE"
}

log_error() {
    echo -e "${RED}[$(date +%H:%M:%S)]${NC} ✗ $1" | tee -a "$LOG_FILE"
}

log_warning() {
    echo -e "${YELLOW}[$(date +%H:%M:%S)]${NC} ⚠ $1" | tee -a "$LOG_FILE"
}

# Check if a service responds with 200 OK
check_health() {
    local url=$1
    local max_wait=${2:-120}  # Maximum wait time in seconds
    local start_time=$(date +%s.%N)
    
    while true; do
        if curl -sf "$url" > /dev/null 2>&1; then
            local end_time=$(date +%s.%N)
            local duration=$(echo "$end_time - $start_time" | bc)
            echo "$duration"
            return 0
        fi
        
        local current_time=$(date +%s.%N)
        local elapsed=$(echo "$current_time - $start_time" | bc)
        
        if (( $(echo "$elapsed > $max_wait" | bc -l) )); then
            echo "-1"
            return 1
        fi
        
        sleep 0.5
    done
}

# Cleanup all containers
cleanup() {
    log "Cleaning up containers..."
    docker-compose down -v 2>/dev/null || true
    docker-compose -f docker-compose.yml down -v 2>/dev/null || true
    
    # Wait for ports to be released
    sleep 2
    
    # Verify ports are free
    if lsof -i :80 > /dev/null 2>&1 || lsof -i :8000 > /dev/null 2>&1 || lsof -i :3000 > /dev/null 2>&1; then
        log_warning "Ports still in use, waiting additional time..."
        sleep 5
    fi
    
    log_success "Cleanup complete"
}

# Run a single benchmark iteration
run_benchmark() {
    local iteration=$1
    
    log "==================================================================="
    log "Starting benchmark iteration $iteration/$ITERATIONS"
    log "==================================================================="
    
    # Start docker-compose and immediately begin timing
    local compose_start=$(date +%s.%N)
    
    log "Starting docker-compose up..."
    docker-compose -f docker-compose.yml up -d --build 2>&1 | tee -a "$LOG_FILE"
    
    local compose_end=$(date +%s.%N)
    local compose_time=$(echo "$compose_end - $compose_start" | bc)
    
    log_success "Docker-compose up completed in ${compose_time}s"
    
    # Check when each service becomes healthy
    log "Checking service health..."
    
    # Nginx (should be fastest)
    log "Waiting for nginx..."
    local nginx_time=$(check_health "$NGINX_HEALTH" 120)
    if [ "$nginx_time" = "-1" ]; then
        log_error "Nginx failed to respond within timeout"
        return 1
    fi
    log_success "Nginx ready in ${nginx_time}s"
    
    # Backend
    log "Waiting for backend..."
    local backend_time=$(check_health "$BACKEND_HEALTH" 120)
    if [ "$backend_time" = "-1" ]; then
        log_error "Backend failed to respond within timeout"
        return 1
    fi
    log_success "Backend ready in ${backend_time}s"
    
    # Frontend
    log "Waiting for frontend..."
    local frontend_time=$(check_health "$FRONTEND_HEALTH" 120)
    if [ "$frontend_time" = "-1" ]; then
        log_error "Frontend failed to respond within timeout"
        return 1
    fi
    log_success "Frontend ready in ${frontend_time}s"
    
    # Calculate total time (max of all services)
    local total_time=$(echo "$nginx_time" | awk '{print $1}')
    if (( $(echo "$backend_time > $total_time" | bc -l) )); then
        total_time=$backend_time
    fi
    if (( $(echo "$frontend_time > $total_time" | bc -l) )); then
        total_time=$frontend_time
    fi
    
    # Test actual user request through nginx
    log "Testing end-to-end request through nginx..."
    local e2e_start=$(date +%s.%N)
    if curl -sf "${NGINX_URL}/" > /dev/null 2>&1; then
        local e2e_end=$(date +%s.%N)
        local e2e_time=$(echo "$e2e_end - $compose_start" | bc)
        log_success "End-to-end request completed in ${e2e_time}s from compose start"
    else
        log_error "End-to-end request failed"
        e2e_time="-1"
    fi
    
    # Output results in JSON format
    cat >> "$RESULTS_FILE.tmp" <<EOF
{
  "iteration": $iteration,
  "timestamp": "$(date -Iseconds)",
  "compose_time": $compose_time,
  "nginx_time": $nginx_time,
  "backend_time": $backend_time,
  "frontend_time": $frontend_time,
  "total_time": $total_time,
  "e2e_time": $e2e_time
}
EOF
    
    if [ $iteration -lt $ITERATIONS ]; then
        echo "," >> "$RESULTS_FILE.tmp"
    fi
    
    log "==================================================================="
    log "Iteration $iteration complete"
    log "  Compose:  ${compose_time}s"
    log "  Nginx:    ${nginx_time}s"
    log "  Backend:  ${backend_time}s"
    log "  Frontend: ${frontend_time}s"
    log "  Total:    ${total_time}s"
    log "  E2E:      ${e2e_time}s"
    log "==================================================================="
    
    # Cleanup for next iteration
    if [ $iteration -lt $ITERATIONS ]; then
        log "Waiting before next iteration..."
        sleep 5
        cleanup
        sleep 5
    fi
}

# Calculate and display statistics
calculate_stats() {
    log "==================================================================="
    log "Calculating statistics..."
    log "==================================================================="
    
    # Finalize JSON array
    echo "[" > "$RESULTS_FILE"
    cat "$RESULTS_FILE.tmp" >> "$RESULTS_FILE"
    echo "]" >> "$RESULTS_FILE"
    rm "$RESULTS_FILE.tmp"
    
    # Calculate averages using Python
    python3 - "$RESULTS_FILE" <<'PYTHON'
import json
import sys
from statistics import mean, stdev

with open(sys.argv[1], 'r') as f:
    data = json.load(f)

metrics = ['compose_time', 'nginx_time', 'backend_time', 'frontend_time', 'total_time', 'e2e_time']

print("\n" + "="*70)
print("BENCHMARK RESULTS SUMMARY")
print("="*70)

for metric in metrics:
    values = [float(d[metric]) for d in data if float(d[metric]) > 0]
    if values:
        avg = mean(values)
        std = stdev(values) if len(values) > 1 else 0
        min_val = min(values)
        max_val = max(values)
        
        metric_name = metric.replace('_', ' ').title()
        print(f"\n{metric_name}:")
        print(f"  Average: {avg:.3f}s")
        print(f"  Std Dev: {std:.3f}s")
        print(f"  Min:     {min_val:.3f}s")
        print(f"  Max:     {max_val:.3f}s")

print("\n" + "="*70)
print(f"Results saved to: {sys.argv[1]}")
print("="*70 + "\n")
PYTHON
}

# ==============================================================================
# Main Script
# ==============================================================================

main() {
    # Setup
    mkdir -p "$RESULTS_DIR"
    log "Container Startup Benchmark"
    log "==================================================================="
    log "Iterations: $ITERATIONS"
    log "Results file: $RESULTS_FILE"
    log "Log file: $LOG_FILE"
    log "==================================================================="
    
    # Initial cleanup
    cleanup
    
    # Run benchmarks
    for i in $(seq 1 $ITERATIONS); do
        if ! run_benchmark $i; then
            log_error "Benchmark iteration $i failed"
            cleanup
            exit 1
        fi
    done
    
    # Final cleanup
    log "All iterations complete, cleaning up..."
    cleanup
    
    # Calculate and display statistics
    calculate_stats
    
    log_success "Benchmark complete!"
}

# Trap to ensure cleanup on exit
trap cleanup EXIT INT TERM

main
