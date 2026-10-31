#!/bin/bash
# Follow today's agent log. Pass a date (YYYY-MM-DD) to follow another day's log.
set -euo pipefail

cd /Users/keithfry/projects/techradar

LOG_DATE="${1:-$(date +%Y-%m-%d)}"
LOG_FILE="logs/techradar-agent-${LOG_DATE}.log"

if [ ! -f "$LOG_FILE" ]; then
    echo "Waiting for $LOG_FILE to appear..." >&2
fi

# -F keeps retrying if the file doesn't exist yet or gets recreated.
exec tail -F "$LOG_FILE"
