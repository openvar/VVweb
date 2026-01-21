#!/usr/bin/env bash
set -euo pipefail
set -x  # <<< Trace all commands

PROJECT_ROOT="/local/VVweb"
SUPERVISORD_CONF="$PROJECT_ROOT/supervisord.conf"

# --- RabbitMQ config ---
COOKIE_FILE="$PROJECT_ROOT/.erlang.cookie"

# Create cookie if missing (owner-only)
if [ ! -f "$COOKIE_FILE" ]; then
  echo "Generating RabbitMQ cookie in $PROJECT_ROOT..."
  head -c 20 /dev/urandom | base64 > "$COOKIE_FILE"
  chmod 400 "$COOKIE_FILE"
fi

# Export ERLANG_COOKIE for this session
export ERLANG_COOKIE="$COOKIE_FILE"

# --- RabbitMQ debug paths ---
export RABBITMQ_MNESIA_BASE="$PROJECT_ROOT/mnesia"
export RABBITMQ_LOG_BASE="$PROJECT_ROOT/logs/rabbitmq"
mkdir -p "$RABBITMQ_MNESIA_BASE" "$RABBITMQ_LOG_BASE"

# Start RabbitMQ if not running (debug mode)
if ! rabbitmq-diagnostics -q ping >/dev/null 2>&1; then
  echo "RabbitMQ not running, starting..."

  # Run RabbitMQ in foreground with debug log
  rabbitmq-server -detached -kernel error_logger '{file,"'$PROJECT_ROOT'/logs/rabbit_debug.log"}' \
    -mnesia dir "$RABBITMQ_MNESIA_BASE" || {
        echo "ERROR: RabbitMQ failed to start!"
        tail -n 50 "$PROJECT_ROOT/logs/rabbit_debug.log"
        exit 1
    }

  echo "Waiting for RabbitMQ to become fully ready..."
  for i in {1..90}; do
    if rabbitmq-diagnostics -q ping >/dev/null 2>&1; then
      echo "RabbitMQ is fully up."
      break
    fi
    sleep 1
  done

  if ! rabbitmq-diagnostics -q ping >/dev/null 2>&1; then
    echo "WARNING: RabbitMQ did not become fully ready within timeout. Check logs:"
    tail -n 50 "$PROJECT_ROOT/logs/rabbit_debug.log"
  fi
else
  echo "RabbitMQ already running."
fi
