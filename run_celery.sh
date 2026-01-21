#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/local/VVweb"
SUPERVISORD_CONF="$PROJECT_ROOT/supervisord.conf"

# --- RabbitMQ config ---
COOKIE_FILE="$PROJECT_ROOT/.erlang.cookie"
NODE_NAME="rabbit@$(hostname -s)"

# Create cookie if missing (owner-only)
if [ ! -f "$COOKIE_FILE" ]; then
  echo "Generating RabbitMQ cookie..."
  head -c 20 /dev/urandom | base64 > "$COOKIE_FILE"
  chmod 400 "$COOKIE_FILE"
fi

# --- Force environment for RabbitMQ ---
export ERLANG_COOKIE="$COOKIE_FILE"
export HOME="$PROJECT_ROOT"

# --- Start RabbitMQ if not running ---
if ! rabbitmq-diagnostics -q ping --node "$NODE_NAME" >/dev/null 2>&1; then
  echo "RabbitMQ not running, starting..."
  rabbitmq-server -detached --node "$NODE_NAME"

  echo "Waiting for RabbitMQ to become fully ready..."
  for i in {1..90}; do
    if rabbitmq-diagnostics -q ping --node "$NODE_NAME" >/dev/null 2>&1; then
      echo "RabbitMQ is fully up."
      break
    fi
    sleep 1
  done

  # final check
  if ! rabbitmq-diagnostics -q ping --node "$NODE_NAME" >/dev/null 2>&1; then
    echo "WARNING: RabbitMQ did not become fully ready within timeout. Continuing..."
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

# <LICENSE>
# Copyright (C) 2016-2026 VariantValidator Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
# </LICENSE>
