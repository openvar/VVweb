ps aux | grep celery

echo ActiveTasks
celery inspect active

echo ReservedTasks
celery inspect reserved

echo ScheduledTasks
celery inspect scheduled

