#!/usr/bin/env bash
#
# Start supervisord with the project supervisord.conf
# supervisord will manage Celery worker and beat processes.
#
# Usage:
#   ./run_celery.sh
#
# Make sure supervisord.conf is configured to launch Celery properly.

set -e

# Set your full absolute project root path here
PROJECT_ROOT="/local/VVweb"

# Path to supervisord config file
SUPERVISORD_CONF="$PROJECT_ROOT/supervisord.conf"

echo "Starting supervisord with config: $SUPERVISORD_CONF"

# Start supervisord in foreground so you can see logs and ctrl-c to stop
# Use -n option to run in foreground (no daemonize)
supervisord -n -c "$SUPERVISORD_CONF"
