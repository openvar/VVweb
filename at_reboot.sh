sleep 30
source /local/miniconda3/bin/activate vvweb_v2
cd /local/VVweb
./run_celery.sh
echo "test" |mail -s "$HOSTNAME VVWeb INFO Celery has been started (at_reboot.sh)" peter.j.freeman@manchester.ac.uk 