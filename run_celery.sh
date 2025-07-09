#!/usr/bin/env bash
#
# Start supervisord with the project supervisord.conf if not already running.
#

set -e

PROJECT_ROOT="/local/VVweb"
SUPERVISORD_CONF="$PROJECT_ROOT/supervisord.conf"

# Check if supervisord is already running
if pgrep -f "supervisord.*$SUPERVISORD_CONF" > /dev/null; then
  echo "Supervisord is already running."
else
  echo "Starting supervisord with config: $SUPERVISORD_CONF"
  supervisord -c "$SUPERVISORD_CONF"
  echo "Supervisord started in background."
fi
