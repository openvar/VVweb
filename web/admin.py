from django.contrib import admin
from . import models
from django_celery_results.models import TaskResult
from django_celery_results.admin import TaskResultAdmin as DefaultTaskResultAdmin
import json
from django.contrib.auth import get_user_model

User = get_user_model()

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
# -------------------------------------------------------------------
def parse_result(obj):
    """
    Returns a dict parsed safely from TaskResult.result.
    Never crashes.

    Handles:
    - None, empty strings
    - invalid JSON
    - bytes
    - dicts
    - legacy string formats
    """
    try:
        data = obj.result

        if not data:
            return {}

        # Already a dict
        if isinstance(data, dict):
            return data

        # Decode bytes
        if isinstance(data, bytes):
            data = data.decode("utf-8", errors="ignore")

        # Parse JSON encoded as string
        if isinstance(data, str):
            try:
                return json.loads(data)
            except Exception:
                return {}

        return {}

    except Exception:
        return {}


# -------------------------------------------------------------------
# ADMIN ACTION: Show username(s) for selected tasks
# -------------------------------------------------------------------
@admin.action(description="Show username(s) for selected tasks")
def show_usernames(modeladmin, request, queryset):
    """
    Look up usernames from user_id inside result JSON.
    Report usernames in the Django admin message system.
    """
    for tr in queryset:
        data = parse_result(tr)
        uid = data.get("user_id")

        # System task
        if not uid:
            modeladmin.message_user(
                request,
                f"Task {tr.task_id}: SYSTEM TASK (no user_id)"
            )
            continue

        # Real user
        try:
            user = User.objects.get(id=uid)
            modeladmin.message_user(
                request,
                f"Task {tr.task_id}: username = {user.username}, email = {user.email}"
            )
        except User.DoesNotExist:
            modeladmin.message_user(
                request,
                f"Task {tr.task_id}: user_id {uid} does NOT exist"
            )


# -------------------------------------------------------------------
# Custom TaskResult admin
# -------------------------------------------------------------------
@admin.register(TaskResult)
class TaskResultAdmin(DefaultTaskResultAdmin):

    # -------------------------------------------------------------------
    # Performance + Usability improvements
    # -------------------------------------------------------------------

    # NEW: Default ordering → newest tasks first
    ordering = ("-date_done",)

    # NEW: Do not load giant "result" JSON blobs unnecessarily
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.defer("result")

    # -------------------------------------------------------------------
    # Display columns
    # -------------------------------------------------------------------
    list_display = (
        "task_id",
        "safe_task_name",
        "status",
        "date_done",
        "safe_user_id",
        "safe_email",
        "safe_username",   # NEW username column
    )

    search_fields = ("task_id", "status", "result")
    list_filter = ("status", "date_done")

    actions = [show_usernames]

    # -------------------------------------------------------------------
    # Accessor methods
    # -------------------------------------------------------------------

    def safe_user_id(self, obj):
        data = parse_result(obj)
        return data.get("user_id", "-")
    safe_user_id.short_description = "User ID"

    def safe_email(self, obj):
        data = parse_result(obj)
        return data.get("email", "-")
    safe_email.short_description = "Email"

    def safe_task_name(self, obj):
        data = parse_result(obj)
        return data.get("task_name", "-")
    safe_task_name.short_description = "Task Name"

    def safe_username(self, obj):
        """
        New column: show the username associated with user_id.
        """
        data = parse_result(obj)
        uid = data.get("user_id")

        if not uid:
            return "SYSTEM"

        try:
            return User.objects.get(id=uid).username
        except User.DoesNotExist:
            return f"(missing: {uid})"

    safe_username.short_description = "Username"

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