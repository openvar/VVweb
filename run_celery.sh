#!/usr/bin/env bash

set -e

PROJECT_ROOT="/local/VVweb"
SUPERVISORD_CONF="$PROJECT_ROOT/supervisord.conf"
SUPERVISOR_PID="$PROJECT_ROOT/supervisord.pid"
SUPERVISOR_SOCK="$PROJECT_ROOT/supervisord.sock"

echo "Using supervisord config: $SUPERVISORD_CONF"

##############################################################################
# 1. HARD STOP (DO NOT USE supervisorctl shutdown)
##############################################################################

echo "Stopping all running services..."

# Kill supervisord safely using PID file
if [ -f "$SUPERVISOR_PID" ]; then
    kill $(cat "$SUPERVISOR_PID") 2>/dev/null || true
    echo "Supervisord stopped"
fi

# Kill any leftover celery safely
pkill -f celery || true

sleep 2

##############################################################################
# 2. CLEAN stale state
##############################################################################

echo "Cleaning stale files..."

rm -f "$SUPERVISOR_PID"
rm -f "$SUPERVISOR_SOCK"
rm -f "$PROJECT_ROOT/celery_worker.pid"
rm -f "$PROJECT_ROOT/celery_beat.pid"

##############################################################################
# 3. START fresh supervisor
##############################################################################

echo "Starting supervisord..."
supervisord -c "$SUPERVISORD_CONF"

# Wait for supervisory socket
for i in {1..10}; do
    if [ -S "$SUPERVISOR_SOCK" ]; then
        break
    fi
    sleep 1
done

##############################################################################
# 4. START celery processes
##############################################################################

echo "Starting Celery worker..."
supervisorctl -c "$SUPERVISORD_CONF" start celery_worker || true

echo "Starting Celery beat..."
supervisorctl -c "$SUPERVISORD_CONF" start celery_beat || true

##############################################################################
# 5. VERIFY
##############################################################################

if pgrep -f "celery.*worker" > /dev/null; then
    echo "✅ Celery worker running"
else
    echo "❌ ERROR: Celery worker not running"
    exit 1
fi

echo "✅ Restart complete"

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
