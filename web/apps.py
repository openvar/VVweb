# web/apps.py
from django.apps import AppConfig
import logging

logger = logging.getLogger("vv")


class WebConfig(AppConfig):
    name = "web"

    def ready(self):
        # Ensure Celery tasks are registered
        try:
            from . import tasks  # noqa: F401
            logger.info("web.tasks imported – Celery tasks registered")
        except Exception as e:
            logger.error("Failed to import web.tasks: %s", e)

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
