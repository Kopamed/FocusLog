#!/usr/bin/env bash
# Launch FocusLog web dashboard

export PYTHONPATH="${PYTHONPATH}:$(dirname "$0")/src"

echo "🎯 Starting FocusLog Dashboard..."
echo "Open http://localhost:5000 in your browser"
echo ""

python3 src/dashboard/app.py
