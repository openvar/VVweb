#!/bin/bash

# echo "test" |mail -s "$HOSTNAME VVweb restart test STARTED" peter.j.freeman@manchester.ac.uk
source /local/miniconda3/bin/activate vvweb  
out=$(/local/VVweb/check_celery_status.sh |grep -A2 ^ActiveTasks |tail -1)
test=$(echo $out | grep -c "\- empty \-")

if [ $test -eq 1 ]
then
   ps aux | grep celery | awk '{print $2}' | xargs kill
   # echo "test" |mail -s "$HOSTNAME VVWeb CELERY KILLED" peter.j.freeman@manchester.ac.uk
   sleep 30
   source /local/miniconda3/bin/activate vvweb
   cd /local/VVweb
   ./run_celery.sh
   echo "test" |mail -s "$HOSTNAME VVWeb CELERY test and restart script complete" peter.j.freeman@manchester.ac.uk
else
   echo "test" |mail -s "$HOSTNAME VVweb ABORT CELERY RESTART JOB RUNNING" peter.j.freeman@manchester.ac.uk
fi
