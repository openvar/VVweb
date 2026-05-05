#!/usr/bin/env bash

set -e

PROJECT_ROOT="/local/VVweb"
SUPERVISORD_CONF="$PROJECT_ROOT/supervisord.conf"
SUPERVISOR_PID="$PROJECT_ROOT/supervisord.pid"
SUPERVISOR_SOCK="$PROJECT_ROOT/supervisord.sock"

echo "Using supervisord config: $SUPERVISORD_CONF"

##############################################################################
# 1. If supervisord is running → STOP EVERYTHING CLEANLY
##############################################################################

if pgrep -f "supervisord.*$SUPERVISORD_CONF" > /dev/null 2>&1; then
    echo "Supervisord running — stopping Celery and supervisord..."

    supervisorctl -c "$SUPERVISORD_CONF" stop celery_worker || true
    supervisorctl -c "$SUPERVISORD_CONF" stop celery_beat || true

    supervisorctl -c "$SUPERVISORD_CONF" shutdown || true

    # 🔴 Added: ensure NO stale processes remain
    pkill -f celery || true
    pkill -f supervisord || true

    sleep 2
fi

##############################################################################
# 2. Clean stale files
##############################################################################

echo "Cleaning stale files..."

rm -f "$SUPERVISOR_PID"
rm -f "$SUPERVISOR_SOCK"
rm -f "$PROJECT_ROOT/celery_worker.pid"
rm -f "$PROJECT_ROOT/celery_beat.pid"

##############################################################################
# 3. Start supervisord fresh
##############################################################################

echo "Starting supervisord..."
supervisord -c "$SUPERVISORD_CONF"

sleep 2

##############################################################################
# 4. Start Celery services
##############################################################################

echo "Starting Celery worker..."
supervisorctl -c "$SUPERVISORD_CONF" start celery_worker

echo "Starting Celery beat..."
supervisorctl -c "$SUPERVISORD_CONF" start celery_beat

echo "All services started successfully."

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
