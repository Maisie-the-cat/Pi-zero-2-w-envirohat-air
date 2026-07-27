#!/bin/bash
set -e

echo "=========================================="
echo "Running Tests for Enviro+ Air HAT Logger"
echo "=========================================="
echo ""

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    echo "pytest not found. Installing..."
    pip install pytest
fi

# Run tests
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

echo "Running configuration tests..."
pytest tests/test_config.py -v --tb=short

echo ""
echo "Running database tests..."
pytest tests/test_database.py -v --tb=short

echo ""
echo "=========================================="
echo "All tests completed!"
echo "=========================================="
