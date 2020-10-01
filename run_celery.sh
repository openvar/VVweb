#!/usr/bin/env bash

celery beat -A VVweb -l error --scheduler django_celery_beat.schedulers.DatabaseScheduler --detach --logfile logs/celery/beat.log --pidfile celerybeat.pid

celery worker -A VVweb -l error --detach --logfile logs/celery/%n%I.log --pidfile celeryd.pid

