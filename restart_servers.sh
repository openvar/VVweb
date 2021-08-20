#!/usr/bin/env bash

# Stop Apache
sudo systemctl stop httpd

# Start environment
conda activate vvweb

# Stop celery
ps aux | grep celery | awk '{print $2}' | xargs kill

# Purge the batch queue
celery purge

# Stop RabbitMQ
sudo systemctl stop rabbitmq-server

# Restart database servers
sudo systemctl restart postgresql-11
sudo systemctl restart mariadb

# Start RabbitMQ
sudo systemctl start rabbitmq-server

# Start celery
celery beat -A VVweb -l error --scheduler django_celery_beat.schedulers.DatabaseScheduler --detach --logfile logs/celery/beat.log --pidfile celerybeat.pid
celery worker -A VVweb -l error --detach --logfile logs/celery/%n%I.log --pidfile celeryd.pid

# Start Apache
sudo systemctl start httpd

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
