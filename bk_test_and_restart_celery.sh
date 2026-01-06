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
