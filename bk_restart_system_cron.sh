# VVweb restart procedure
echo "test" |mail -s "$HOSTNAME VVweb restart script ACTIVATED" peter.j.freeman@manchester.ac.uk 
sudo -u wwwrun bash
echo "test" |mail -s "$HOSTNAME VVweb wwwrun ACTIVATED" peter.j.freeman@manchester.ac.uk
cd /local/VVweb
source /local/miniconda3/bin/activate vvweb

echo "test" |mail -s "$HOSTNAME VVweb kill celery" peter.j.freeman@manchester.ac.uk
./kill_celery.sh
echo "test" |mail -s "$HOSTNAME VVweb killed" peter.j.freeman@manchester.ac.uk
sleep 30
echo "test" |mail -s "$HOSTNAME VVweb start celery" peter.j.freeman@manchester.ac.uk
./run_celery.sh
exit

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
