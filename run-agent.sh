#!/bin/bash
# launchd wrapper: launchd plist paths can't use strftime, so stamp the
# log filename here, then run the scan and the tuner.
set -euo pipefail

# launchd starts jobs with a minimal PATH (/usr/bin:/bin:/usr/sbin:/sbin).
# The tuner runs the ollama command, which lives in /usr/local/bin.
export PATH="/usr/local/bin:/opt/homebrew/bin:$PATH"

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

# Run the scan, keep its exit status, and never let set -e stop the script here.
status=0
/opt/homebrew/bin/uv run run.py --config config/config.toml --time 08:00 "$@" >>"$LOG_FILE" 2>&1 || status=$?

# Tune after the scan, even when it failed: the tuner judges whatever evidence
# was recorded. A tuner failure is logged and never changes the exit status.
PYTHONUNBUFFERED=1 /opt/homebrew/bin/uv run run.py tune --config config/config.toml --date "$LOG_DATE" >>"$LOG_FILE" 2>&1 || echo "tuner failed (exit $?)" >>"$LOG_FILE"

exit "$status"
