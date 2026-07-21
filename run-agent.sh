#!/bin/bash
# launchd wrapper: launchd plist paths can't use strftime, so stamp the
# log filename here before exec'ing the real run.
set -euo pipefail

cd /Users/keithfry/projects/techradar
mkdir -p logs

LOG_FILE="logs/techradar-agent-$(date +%Y-%m-%d).log"

exec /opt/homebrew/bin/uv run run.py --config config/topics.toml "$@" >>"$LOG_FILE" 2>&1
