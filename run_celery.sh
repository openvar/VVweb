#!/usr/bin/env bash

set -e

PROJECT_ROOT="/local/VVweb"
SUPERVISORD_CONF="$PROJECT_ROOT/supervisord.conf"
SUPERVISOR_SOCK="$PROJECT_ROOT/supervisord.sock"

echo "Using supervisord config: $SUPERVISORD_CONF"

##############################################################################
# 1. Ensure supervisord is running
##############################################################################

if [ ! -S "$SUPERVISOR_SOCK" ]; then
    echo "Supervisord not running — starting fresh..."

    rm -f "$PROJECT_ROOT/supervisord.pid"
    rm -f "$SUPERVISOR_SOCK"

    supervisord -c "$SUPERVISORD_CONF"

    sleep 2
fi

##############################################################################
# 2. Restart Celery processes ONLY (safe)
##############################################################################

echo "Restarting Celery services..."

supervisorctl -c "$SUPERVISORD_CONF" stop celery_worker || true
supervisorctl -c "$SUPERVISORD_CONF" stop celery_beat || true

sleep 1

supervisorctl -c "$SUPERVISORD_CONF" start celery_worker
supervisorctl -c "$SUPERVISORD_CONF" start celery_beat

##############################################################################
# 3. Verify
##############################################################################

if pgrep -f "celery.*worker" > /dev/null; then
    echo "✅ Celery worker running"
else
    echo "❌ ERROR: Worker not running"
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

