#!/bin/bash
cd /root/deliverydash
LOG_FILE="/root/deliverydash/logs/keepalive.log"
mkdir -p "$(dirname "$LOG_FILE")"

echo "=== $(date) ===" >> "$LOG_FILE"
xvfb-run -a ./venv/bin/python glovo_keepalive.py >> "$LOG_FILE" 2>&1
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo "FAILED with exit code $EXIT_CODE" >> "$LOG_FILE"
fi
echo "" >> "$LOG_FILE"
