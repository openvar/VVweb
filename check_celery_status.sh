#!/usr/bin/env bash
set -euo pipefail

TARGET_USER="wwwrun"

echo "Celery processes:"
sudo -u "$TARGET_USER" ps aux | grep '[c]elery'

echo
echo "ActiveTasks:"
sudo -u "$TARGET_USER" celery inspect active || echo "Celery workers not reachable"

echo
echo "ReservedTasks:"
sudo -u "$TARGET_USER" celery inspect reserved || echo "Celery workers not reachable"

echo
echo "ScheduledTasks:"
sudo -u "$TARGET_USER" celery inspect scheduled || echo "Celery workers not reachable"

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
