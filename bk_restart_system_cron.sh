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