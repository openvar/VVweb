from django.contrib import admin
from . import models

from django_celery_results.models import TaskResult
from django_celery_results.admin import TaskResultAdmin as DefaultTaskResultAdmin


# -------------------------------------------------------------------
# Register your own models
# -------------------------------------------------------------------
admin.site.register(models.Contact)


# -------------------------------------------------------------------
# Unregister the default TaskResult admin to avoid AlreadyRegistered
# -------------------------------------------------------------------
try:
    admin.site.unregister(TaskResult)
except admin.sites.NotRegistered:
    pass


# -------------------------------------------------------------------
# Custom TaskResult admin with user_id column
# -------------------------------------------------------------------
@admin.register(TaskResult)
class TaskResultAdmin(DefaultTaskResultAdmin):
    """
    Overrides the default django-celery-results admin to add user_id display.
    """

    list_display = (
        "task_id",
        "status",
        "date_done",
        "get_user_id",
    )

    search_fields = ("task_id", "status", "meta")
    list_filter = ("status", "date_done")

    def get_user_id(self, obj):
        """
        Extract user_id from the meta JSON field.
        """
        try:
            meta = obj.meta or {}
            return meta.get("user_id", "-")
        except Exception:
            return "-"

    get_user_id.short_description = "User ID"


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