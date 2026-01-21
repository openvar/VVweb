#!/usr/bin/env bash
set -euo pipefail

# --- RabbitMQ config ---
COOKIE_FILE="/local/VVweb/.erlang.cookie"
export ERLANG_COOKIE="$COOKIE_FILE"

# --- RabbitMQ directories ---
export RABBITMQ_MNESIA_BASE="/local/VVweb/mnesia"
export RABBITMQ_LOG_BASE="/local/VVweb/logs/rabbitmq"

# Check RabbitMQ status
if rabbitmq-diagnostics -q ping >/dev/null 2>&1; then
    echo "RabbitMQ is running."
    rabbitmqctl status
else
    echo "RabbitMQ is not running."
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
