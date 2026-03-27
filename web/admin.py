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
# Safe JSON parser for TaskResult.result
# This function MUST NEVER crash — admin list view depends on it
# -------------------------------------------------------------------
def parse_result(obj):
    """
    Returns a dict safely parsed from TaskResult.result.
    Handles:
    - None
    - empty strings
    - invalid JSON
    - lists
    - bytes
    - old Celery result formats
    - truncated data
    """
    try:
        res = obj.result

        # Handle None, "", 0, False
        if not res:
            return {}

        # Already a dict
        if isinstance(res, dict):
            return res

        # Bytes → decode silently
        if isinstance(res, bytes):
            try:
                res = res.decode("utf-8", errors="ignore")
            except Exception:
                return {}

        # Strings → try JSON
        if isinstance(res, str):
            try:
                return json.loads(res)
            except Exception:
                return {}

        # Anything unrecognized → fail silently
        return {}

    except Exception:
        return {}

# -------------------------------------------------------------------
# Custom admin for TaskResult
# -------------------------------------------------------------------
@admin.register(TaskResult)
class TaskResultAdmin(DefaultTaskResultAdmin):

    list_display = (
        "task_id",
        "safe_task_name",
        "status",
        "date_done",
        "safe_user_id",
        "safe_email",
    )

    search_fields = ("task_id", "status", "result")
    list_filter = ("status", "date_done")

    # -------------------------------------------------------------------
    # Safe accessors for admin list view
    # -------------------------------------------------------------------
    def safe_user_id(self, obj):
        try:
            data = parse_result(obj)
            return data.get("user_id", "-")
        except Exception:
            return "-"
    safe_user_id.short_description = "User ID"

    def safe_email(self, obj):
        try:
            data = parse_result(obj)
            return data.get("email", "-")
        except Exception:
            return "-"
    safe_email.short_description = "Email"

    def safe_task_name(self, obj):
        try:
            data = parse_result(obj)
            return data.get("task_name", "-")
        except Exception:
            return "-"
    safe_task_name.short_description = "Task Name"


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
