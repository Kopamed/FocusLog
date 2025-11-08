#!/usr/bin/env bash
# Simple launcher script for FocusLog daemon

# Add src directory to PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:$(dirname "$0")/src"

# Run the daemon with all arguments passed through
python3 src/focuslogd/daemon.py "$@"
