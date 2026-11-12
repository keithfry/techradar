#!/usr/bin/env bash
set -euo pipefail

# Configuration
SSH_HOST="techradar-deploy"
LOCAL_BUILD_DIR="./techradar"

# Verify the local source directory exists before syncing
if [[ ! -d "$LOCAL_BUILD_DIR" ]]; then
  echo "Error: Local directory '$LOCAL_BUILD_DIR' not found." >&2
  exit 1
fi

echo "Mirroring $LOCAL_BUILD_DIR/ to /var/www/html/techradar/..."

# Mirror local ./techradar/ contents directly into /var/www/html/techradar/
# --delete removes any remote files/folders that no longer exist locally
rsync -avz --delete \
  "$LOCAL_BUILD_DIR/" \
  "${SSH_HOST}:/var/www/html/techradar/"

echo "Mirror complete: https://keithfry.net/techradar/"