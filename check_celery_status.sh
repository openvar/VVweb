#!/usr/bin/env bash
set -euo pipefail

# Export ERLANG_COOKIE for RabbitMQ if needed
export ERLANG_COOKIE="$HOME/.erlang.cookie"

# Show running Celery processes
echo "Celery processes:"
ps aux | grep celery | grep -v grep || echo "No Celery processes found."

# Inspect tasks
echo -e "\nActiveTasks"
celery -A VVweb inspect active || echo "Could not inspect active tasks."

echo -e "\nReservedTasks"
celery -A VVweb inspect reserved || echo "Could not inspect reserved tasks."

echo -e "\nScheduledTasks"
celery -A VVweb inspect scheduled || echo "Could not inspect scheduled tasks."

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
