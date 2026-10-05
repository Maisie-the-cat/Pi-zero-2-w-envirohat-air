#!/bin/bash
set -euo pipefail

echo "=========================================="
echo "Running Tests for Enviro+ Air HAT Logger"
echo "=========================================="
echo ""

# Use the active Python environment and never install packages at runtime.
PYTHON="${PYTHON:-python3}"
if ! command -v "$PYTHON" &> /dev/null; then
    echo "Python interpreter not found: $PYTHON" >&2
    exit 1
fi
if ! "$PYTHON" -c 'import pytest' &> /dev/null; then
    echo "pytest is not installed for $PYTHON; install the test dependencies before running this script" >&2
    exit 1
fi

# Run tests
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."

echo "Running all tests..."
"$PYTHON" -m pytest tests/ -v --tb=short

echo ""
echo "=========================================="
echo "All tests completed!"
echo "=========================================="
