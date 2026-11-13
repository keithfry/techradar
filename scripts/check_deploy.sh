#!/usr/bin/env bash
# Check that the deploy host is reachable before running deploy_techradar.sh.
# Usage: bash scripts/check_deploy.sh
set -uo pipefail

SSH_HOST="techradar-deploy"
REMOTE_DIR="/var/www/html/techradar"

echo "Public IPv6: $(curl -6 -s -m 5 ifconfig.me || echo 'none')"
echo "Allowed:     2601:408:c000::/40"
echo

echo "Testing SSH to $SSH_HOST..."
if ssh -o ConnectTimeout=10 -o BatchMode=yes "$SSH_HOST" "test -w $REMOTE_DIR"; then
  echo "OK: SSH works and $REMOTE_DIR is writable. Safe to run deploy_techradar.sh."
  exit 0
fi

status=$?
if [[ $status -eq 255 ]]; then
  echo "FAIL: SSH could not connect. If it timed out, your IP is probably outside the firewall rule."
else
  echo "FAIL: SSH connected, but $REMOTE_DIR is missing or not writable."
fi
exit 1
