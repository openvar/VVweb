#!/usr/bin/env bash
#
# Updated for Celery 5+ syntax and no --detach (run in foreground or background yourself)

# Start beat (use & to run in background)
celery -A VVweb beat -l error --scheduler django_celery_beat.schedulers.DatabaseScheduler --logfile logs/celery/beat.log --pidfile celerybeat.pid &

# Start worker (run in background)
celery -A VVweb worker -l error --logfile logs/celery/%n%I.log --pidfile celeryd.pid &

# <LICENSE>
# Copyright (C) 2016-2025 VariantValidator Contributors
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