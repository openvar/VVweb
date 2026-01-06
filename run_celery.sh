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
