#!/usr/bin/env bash
#
# 2021-08-05 (Liam) Removed --detach option as there's a bug in Celery 4.4.7.
# These are the hashed lines

celery beat -A VVweb -l error --scheduler django_celery_beat.schedulers.DatabaseScheduler --detach --logfile logs/celery/beat.log --pidfile celerybeat.pid
# celery beat -A VVweb -l error --scheduler django_celery_beat.schedulers.DatabaseScheduler --logfile logs/celery/beat.log --pidfile celerybeat.pid &

celery worker -A VVweb -l error --detach --logfile logs/celery/%n%I.log --pidfile celeryd.pid
# celery worker -A VVweb -l error --logfile logs/celery/%n%I.log --pidfile celeryd.pid &
