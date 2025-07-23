#!/usr/bin/env bash
#
# Start supervisord with the project supervisord.conf if not already running,
# otherwise restart celery worker and beat.
#

set -e

PROJECT_ROOT="/local/VVweb"
SUPERVISORD_CONF="$PROJECT_ROOT/supervisord.conf"

# Check if supervisord is already running with this config
if pgrep -f "supervisord.*$SUPERVISORD_CONF" > /dev/null; then
  echo "Supervisord is already running."
  echo "Restarting celery_worker and celery_beat..."
  supervisorctl -c "$SUPERVISORD_CONF" restart celery_worker celery_beat
else
  echo "Starting supervisord with config: $SUPERVISORD_CONF"
  supervisord -c "$SUPERVISORD_CONF"
  echo "Supervisord started in background."
fi
