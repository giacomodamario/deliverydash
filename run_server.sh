#!/bin/bash
# Run bot with virtual display on headless server
# This allows running a "headed" browser without a physical display
#
# Usage:
#   ./run_server.sh           # Quick sync (5 invoices)
#   ./run_server.sh --full    # Full sync (100 invoices)
#
# Prerequisites:
#   apt-get install xvfb

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Start virtual display
export DISPLAY=:99
Xvfb :99 -screen 0 1920x1080x24 &
XVFB_PID=$!
sleep 2

# Cleanup on exit
cleanup() {
    if [ -n "$XVFB_PID" ]; then
        kill $XVFB_PID 2>/dev/null || true
    fi
}
trap cleanup EXIT

# Run the bot with all arguments passed through
python run_bot.py "$@"
