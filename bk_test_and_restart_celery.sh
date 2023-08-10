#!/bin/bash

echo "test" |mail -s "$HOSTNAME VVweb restart test STARTED" peter.j.freeman@manchester.ac.uk
source /local/miniconda3/bin/activate vvweb
echo "test" |mail -s "$HOSTNAME VVweb environment activated" peter.j.freeman@manchester.ac.uk  

out=$(/local/VVweb/check_celery_status.sh |grep -A2 ^ActiveTasks |tail -1)
test=$(echo $out | grep -c "\- empty \-")
echo "test" |mail -s "$HOSTNAME VVweb Test complete" peter.j.freeman@manchester.ac.uk

if [ $test -eq 1 ]
then
   echo "test" |mail -s "$HOSTNAME VVWeb test passed, restarting" peter.j.freeman@manchester.ac.uk 
   # echo "Not running - run restart script"
   /local/VVweb/restart_system_cron.sh
   echo "test" |mail -s "$HOSTNAME VVWeb restarted" peter.j.freeman@manchester.ac.uk
else
   # echo "Running"
   echo "test" |mail -s "$HOSTNAME VVweb FAILED RESTART" peter.j.freeman@manchester.ac.uk 
fi
