#!/bin/bash
# launchd wrapper: launchd plist paths can't use strftime, so stamp the
# log filename here before exec'ing the real run.
set -euo pipefail

cd /Users/keithfry/projects/techradar
mkdir -p logs

LOG_DATE="$(date +%Y-%m-%d)"
for i in "$@"; do
    case "$i" in
        --date=*) LOG_DATE="${i#--date=}" ;;
        --date) LOG_DATE_NEXT=1 ;;
        *) if [ "${LOG_DATE_NEXT:-0}" = 1 ]; then LOG_DATE="$i"; LOG_DATE_NEXT=0; fi ;;
    esac
done

LOG_FILE="logs/techradar-agent-${LOG_DATE}.log"

exec /opt/homebrew/bin/uv run run.py --config config/config.toml --time 08:00 "$@" >>"$LOG_FILE" 2>&1
