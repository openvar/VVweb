#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/local/VVweb"
SUPERVISORD_CONF="$PROJECT_ROOT/supervisord.conf"

# --- RabbitMQ config ---
RABBIT_HOST="localhost"
RABBIT_PORT="5672"
COOKIE_FILE="$PROJECT_ROOT/.erlang.cookie"

# Create cookie if missing
if [ ! -f "$COOKIE_FILE" ]; then
  echo "Generating RabbitMQ cookie..."
  head -c 20 /dev/urandom | base64 > "$COOKIE_FILE"
  # make it readable/writable by owner and group, readable by others
  chmod 664 "$COOKIE_FILE"
fi

# Export environment for this script only
export ERLANG_COOKIE="$(cat "$COOKIE_FILE")"
export HOME="$PROJECT_ROOT"

# --- Start RabbitMQ if not running ---
if ! rabbitmq-diagnostics -q ping >/dev/null 2>&1; then
  echo "RabbitMQ not running, starting..."
  rabbitmq-server -detached

  echo "Waiting for RabbitMQ to become ready..."
  for i in {1..90}; do
    if rabbitmq-diagnostics -q ping >/dev/null 2>&1; then
      echo "RabbitMQ is up."
      break
    fi
    sleep 1
  done

  if ! rabbitmq-diagnostics -q ping >/dev/null 2>&1; then
    echo "ERROR: RabbitMQ did not become ready within timeout."
    exit 1
  fi
else
  echo "RabbitMQ already running."
fi

# --- Start supervisord / Celery ---
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
