#!/bin/bash
# Manual wrapper for retention.py — prunes old radar episodes for every topic
# in config/config.toml (AI + Robotics): audio artifacts after 3 months
# (90 days), whole episodes (HTML/JSON) after 5 months (150 days).
#
#   ./retention-agent.sh              # purge + regenerate + commit + push
#   ./retention-agent.sh --dry-run    # purge + regenerate on disk, NO commit/push
#
# --dry-run still deletes/edits files on disk so `git status`/`git diff` show
# the real effect; the log ends with the command to revert it.
set -euo pipefail

cd /Users/keithfry/projects/techradar
mkdir -p logs

LOG_FILE="logs/techradar-retention-$(date +%Y-%m-%d).log"

/opt/homebrew/bin/uv run retention.py --config config/config.toml "$@" 2>&1 | tee -a "$LOG_FILE"
