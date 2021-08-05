#!/usr/bin/env bash

# Stop Apache
sudo systemctl stop httpd

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