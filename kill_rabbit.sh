#!/usr/bin/env bash
set -euo pipefail

PORT=25672

echo "Stopping RabbitMQ..."

# Attempt graceful shutdown (ignore failure if node is unreachable)
rabbitmqctl stop >/dev/null 2>&1 || true

# Give it a moment to exit cleanly
sleep 3

# Check if anything is still listening on the RabbitMQ distribution port
pids=$(lsof -ti tcp:${PORT} 2>/dev/null || true)

if [[ -n "${pids}" ]]; then
    echo "RabbitMQ still appears to be running (port ${PORT})."
    echo "Sending SIGTERM to PID(s): ${pids}"
    kill ${pids}

    sleep 5

    # Anything still alive?
    pids=$(lsof -ti tcp:${PORT} 2>/dev/null || true)

    if [[ -n "${pids}" ]]; then
        echo "Processes did not terminate. Sending SIGKILL..."
        kill -9 ${pids}
        sleep 1
    fi
fi

# Final verification
if lsof -ti tcp:${PORT} >/dev/null 2>&1; then
    echo "ERROR: Port ${PORT} is still in use."
    lsof -i tcp:${PORT}
    exit 1
fi

echo "RabbitMQ has been stopped."

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