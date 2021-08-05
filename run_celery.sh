#!/usr/bin/env bash
#
# 2021-08-05 (Liam) Removed --detach option as there's a bug in Celery 4.4.7.
# These are the hashed lines and celery was set to 4.4.6

celery beat -A VVweb -l error --scheduler django_celery_beat.schedulers.DatabaseScheduler --detach --logfile logs/celery/beat.log --pidfile celerybeat.pid
# celery beat -A VVweb -l error --scheduler django_celery_beat.schedulers.DatabaseScheduler --logfile logs/celery/beat.log --pidfile celerybeat.pid &

celery worker -A VVweb -l error --detach --logfile logs/celery/%n%I.log --pidfile celeryd.pid
# celery worker -A VVweb -l error --logfile logs/celery/%n%I.log --pidfile celeryd.pid &

# <LICENSE>
# Copyright (C) 2016-2021 VariantValidator Contributors
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

