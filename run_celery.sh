#!/usr/bin/env bash
#
# Start RabbitMQ (if needed) and supervisord-managed Celery workers.
#

set -euo pipefail

PROJECT_ROOT="/local/VVweb"
SUPERVISORD_CONF="$PROJECT_ROOT/supervisord.conf"

RABBIT_HOST="localhost"
RABBIT_PORT="5672"

echo "=== Checking RabbitMQ ==="

if ! nc -z "$RABBIT_HOST" "$RABBIT_PORT" >/dev/null 2>&1; then
  echo "RabbitMQ not running, starting..."
  rabbitmq-server -detached

  echo "Waiting for RabbitMQ to become ready..."
  for i in {1..30}; do
    if nc -z "$RABBIT_HOST" "$RABBIT_PORT" >/dev/null 2>&1; then
      echo "RabbitMQ is up."
      break
    fi
    sleep 1
  done

  if ! nc -z "$RABBIT_HOST" "$RABBIT_PORT" >/dev/null 2>&1; then
    echo "ERROR: RabbitMQ did not start within timeout."
    exit 1
  fi
else
  echo "RabbitMQ already running."
fi

echo "=== Checking supervisord ==="

if pgrep -f "supervisord.*$SUPERVISORD_CONF" >/dev/null; then
  echo "Supervisord already running."
  echo "Restarting celery_worker and celery_beat..."
  supervisorctl -c "$SUPERVISORD_CONF" restart celery_worker celery_beat
else
  echo "Starting supervisord with config: $SUPERVISORD_CONF"
  supervisord -c "$SUPERVISORD_CONF"
  echo "Supervisord started."
fi

echo "=== Done ==="
