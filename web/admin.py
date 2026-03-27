from django.contrib import admin
from . import models

from django_celery_results.models import TaskResult
from django_celery_results.admin import TaskResultAdmin as DefaultTaskResultAdmin
import json


# -------------------------------------------------------------------
# Register your own models
# -------------------------------------------------------------------
admin.site.register(models.Contact)


# -------------------------------------------------------------------
# Unregister the default TaskResult admin
# -------------------------------------------------------------------
try:
    admin.site.unregister(TaskResult)
except admin.sites.NotRegistered:
    pass


# -------------------------------------------------------------------
# Helper to parse Celery result JSON safely
# -------------------------------------------------------------------
def parse_result(obj):
    """Return result as a dict, even if stored as a JSON string."""
    res = obj.result
    if isinstance(res, dict):
        return res
    if isinstance(res, str):
        try:
            return json.loads(res)
        except Exception:
            return {}
    return {}


# -------------------------------------------------------------------
# Custom TaskResult admin
# -------------------------------------------------------------------
@admin.register(TaskResult)
class TaskResultAdmin(DefaultTaskResultAdmin):

    list_display = (
        "task_id",
        "get_task_name",
        "status",
        "date_done",
        "get_user_id",
        "get_email",
    )

    search_fields = ("task_id", "status", "result")
    list_filter = ("status", "date_done")

    def get_user_id(self, obj):
        data = parse_result(obj)
        return data.get("user_id", "-")
    get_user_id.short_description = "User ID"

    def get_email(self, obj):
        data = parse_result(obj)
        return data.get("email", "-")
    get_email.short_description = "Email"

    def get_task_name(self, obj):
        data = parse_result(obj)
        return data.get("task_name", "-")
    get_task_name.short_description = "Task Name"


# <LICENSE>
# Copyright (C) 2016-2026 VariantValidator Contributors
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see https://www.gnu.org/licenses/
# </LICENSE>