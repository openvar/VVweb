#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="/local/VVweb"
COOKIE_FILE="$PROJECT_ROOT/.erlang.cookie"
NODE_NAME="rabbit@$(hostname -s)"

# Ensure environment matches the running RabbitMQ node
export HOME="$PROJECT_ROOT"
export ERLANG_COOKIE="$(cat "$COOKIE_FILE")"

# Check RabbitMQ status
if rabbitmqctl --node "$NODE_NAME" status >/dev/null 2>&1; then
    echo "RabbitMQ node $NODE_NAME is running."
    rabbitmqctl --node "$NODE_NAME" status
else
    echo "RabbitMQ node $NODE_NAME is not running."
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
