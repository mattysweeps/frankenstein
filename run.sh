#!/bin/bash

# Get the script directory
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$DIR"

echo "================================================="
echo "  🎹 MPK249 Desktop Controller - Launcher"
echo "================================================="

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "Creating python virtual environment..."
    python3 -m venv .venv
fi

# Activate virtual environment
source .venv/bin/activate

# Install/upgrade dependencies if needed
echo "Verifying dependencies..."
pip install -r requirements.txt

# Start the application
echo "Starting application..."
python3 app.py
