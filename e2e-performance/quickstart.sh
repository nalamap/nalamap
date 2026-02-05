#!/bin/bash
# Quick start script for E2E performance testing

set -e

echo "=== E2E Performance Testing Setup ==="
echo ""

# Check if we're in the right directory
if [ ! -f "README.md" ]; then
    echo "Error: Please run this script from the e2e-performance directory"
    exit 1
fi

# Install Python dependencies
echo "Installing Python dependencies..."
pip3 install -q -r requirements.txt

# Generate test data
echo ""
echo "Generating test GeoJSON files..."
python3 utils/generate_test_files.py

# Copy test files to backend uploads directory
echo ""
echo "Copying test files to backend uploads directory..."
mkdir -p ../uploads
cp test_data/*.geojson ../uploads/

# Start the stack
echo ""
echo "Starting E2E test stack..."
echo "This will run: docker compose -f docker-compose.e2e.yml up --build"
echo ""
read -p "Continue? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    docker compose -f docker-compose.e2e.yml up --build -d
    
    echo ""
    echo "Waiting for services to be ready..."
    sleep 10
    
    echo ""
    echo "Services started! You can now run tests:"
    echo "  python3 -m pytest tests/ -v"
    echo ""
    echo "To view logs:"
    echo "  docker compose -f docker-compose.e2e.yml logs -f"
    echo ""
    echo "To stop the stack:"
    echo "  docker compose -f docker-compose.e2e.yml down"
fi
