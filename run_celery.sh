
#!/usr/bin/env bash
#
# Start supervisord with the project supervisord.conf if not already running,
# otherwise restart celery worker and beat. Safe for HPC/managed systems.

set -e

PROJECT_ROOT="/local/VVweb"
SUPERVISORD_CONF="$PROJECT_ROOT/supervisord.conf"
SUPERVISOR_PID="$PROJECT_ROOT/supervisord.pid"
SUPERVISOR_SOCK="$PROJECT_ROOT/supervisord.sock"

echo "Using supervisord config: $SUPERVISORD_CONF"

##############################################################################
# 1. Check if supervisord is actually running with this config
##############################################################################

if pgrep -f "supervisord.*$SUPERVISORD_CONF" > /dev/null 2>&1; then
    echo "Supervisord is already running with this config."
    echo "Restarting Celery services..."
    supervisorctl -c "$SUPERVISORD_CONF" restart celery_worker celery_beat
    exit 0
fi

##############################################################################
# 2. Clean up stale PID and socket files
##############################################################################

echo "Cleaning up stale supervisord files (if any)..."

# Remove stale pidfile if process is dead
if [ -f "$SUPERVISOR_PID" ]; then
    OLD_PID=$(cat "$SUPERVISOR_PID" 2>/dev/null || true)
    if ! ps -p "$OLD_PID" > /dev/null 2>&1; then
        rm -f "$SUPERVISOR_PID"
        echo "Removed stale supervisord.pid"
    fi
fi

# Remove stale socket
rm -f "$SUPERVISOR_SOCK"

# Remove stale Celery pidfiles
rm -f "$PROJECT_ROOT/celery_worker.pid"
rm -f "$PROJECT_ROOT/celery_beat.pid"

##############################################################################
# 3. Start supervisord
##############################################################################

echo "Starting supervisord..."
supervisord -c "$SUPERVISORD_CONF"
echo "Supervisord started."

# Give supervisord a moment to create its socket
sleep 2

##############################################################################
# 4. Start Celery worker and beat
##############################################################################

echo "Starting Celery worker..."
supervisorctl -c "$SUPERVISORD_CONF" start celery_worker

echo "Starting Celery beat..."
supervisorctl -c "$SUPERVISORD_CONF" start celery_beat

echo "All services started successfully."
echo "Use: supervisorctl -c $SUPERVISORD_CONF status"
