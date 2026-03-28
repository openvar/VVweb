from django.contrib import admin
from django.contrib.auth import get_user_model
from django.utils.html import format_html
from django.urls import reverse
import json

from . import models

from django_celery_results.models import TaskResult
from django_celery_results.admin import TaskResultAdmin as DefaultTaskResultAdmin


User = get_user_model()

# -------------------------------------------------------------------
# Register app-specific models
# -------------------------------------------------------------------
admin.site.register(models.Contact)

# -------------------------------------------------------------------
# Unregister default TaskResult admin so we can override it
# -------------------------------------------------------------------
try:
    admin.site.unregister(TaskResult)
except admin.sites.NotRegistered:
    pass

# -------------------------------------------------------------------
# SAFE JSON PARSER — ALWAYS RETURNS A DICT
# -------------------------------------------------------------------
def parse_result(obj):
    """
    Safely parse TaskResult.result. NEVER returns None.
    Handles:
      - None / empty values
      - invalid JSON
      - bytes
      - old Celery pickled formats
    """
    try:
        data = obj.result

        if not data:
            return {}

        if isinstance(data, dict):
            return data

        if isinstance(data, bytes):
            data = data.decode("utf-8", errors="ignore")

        if isinstance(data, str):
            try:
                return json.loads(data)
            except Exception:
                return {}

        return {}

    except Exception:
        return {}

# -------------------------------------------------------------------
# ADMIN ACTION — SHOW USERNAME(S)
# -------------------------------------------------------------------
@admin.action(description="Show username(s) for selected tasks")
def show_usernames(modeladmin, request, queryset):
    for tr in queryset:
        data = parse_result(tr)
        uid = data.get("user_id")

        if not uid:
            modeladmin.message_user(
                request, f"Task {tr.task_id}: SYSTEM TASK (no user_id)"
            )
            continue

        try:
            user = User.objects.get(id=uid)
            modeladmin.message_user(
                request,
                f"Task {tr.task_id}: username={user.username}, email={user.email}"
            )
        except User.DoesNotExist:
            modeladmin.message_user(
                request, f"Task {tr.task_id}: user_id {uid} does NOT exist"
            )

# -------------------------------------------------------------------
# ADMIN ACTION — DISABLE USER ACCOUNTS
# -------------------------------------------------------------------
@admin.action(description="Disable associated user accounts")
def disable_users(modeladmin, request, queryset):
    disabled = 0
    for tr in queryset:
        uid = parse_result(tr).get("user_id")
        if not uid:
            continue
        try:
            user = User.objects.get(id=uid)
            user.is_active = False
            user.save(update_fields=["is_active"])
            disabled += 1
        except User.DoesNotExist:
            pass
    modeladmin.message_user(request, f"Disabled {disabled} user(s).")

# -------------------------------------------------------------------
# ADMIN ACTION — DELETE USER ACCOUNTS
# -------------------------------------------------------------------
@admin.action(description="DELETE associated user accounts (dangerous!)")
def delete_users(modeladmin, request, queryset):
    deleted = 0
    for tr in queryset:
        uid = parse_result(tr).get("user_id")
        if not uid:
            continue
        try:
            User.objects.get(id=uid).delete()
            deleted += 1
        except User.DoesNotExist:
            pass
    modeladmin.message_user(request, f"Deleted {deleted} user account(s).")

# -------------------------------------------------------------------
# CUSTOM TASKRESULT ADMIN
# -------------------------------------------------------------------
@admin.register(TaskResult)
class TaskResultAdmin(DefaultTaskResultAdmin):

    ordering = ("-date_done",)

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.defer("result")  # speeds up admin massively

    list_display = (
        "task_id",
        "safe_task_name",
        "status",
        "date_done",
        "safe_user_id",
        "safe_email",
        "safe_username",
        "user_link",
    )

    list_filter = ("status", "date_done")
    search_fields = ("task_id", "status", "result")
    actions = [show_usernames, disable_users, delete_users]

    # ---- SAFE ACCESSORS ----

    def safe_user_id(self, obj):
        try:
            if obj is None:
                return "-"
            data = parse_result(obj) or {}
            return data.get("user_id", "-")
        except Exception:
            return "-"

    safe_user_id.short_description = "User ID"

    def safe_email(self, obj):
        try:
            if obj is None:
                return "-"
            data = parse_result(obj) or {}
            return data.get("email", "-")
        except Exception:
            return "-"

    safe_email.short_description = "Email"

    def safe_task_name(self, obj):
        try:
            if obj is None:
                return "-"
            data = parse_result(obj) or {}
            if not isinstance(data, dict):
                data = {}
            return data.get("task_name") or obj.task_name or "-"
        except Exception:
            return "-"

    safe_task_name.short_description = "Task Name"

    def safe_username(self, obj):
        try:
            if obj is None:
                return "SYSTEM"
            data = parse_result(obj) or {}
            uid = data.get("user_id")
            if not uid:
                return "SYSTEM"
            try:
                return User.objects.get(id=uid).username
            except User.DoesNotExist:
                return f"(missing {uid})"
        except Exception:
            return "SYSTEM"

    # ---- CLICKABLE LINK TO USER ADMIN PAGE ----

    def user_link(self, obj):
        try:
            uid = parse_result(obj).get("user_id")
        except AttributeError:
            return "SYSTEM"
        try:
            User.objects.get(id=uid)
        except User.DoesNotExist:
            return f"(missing: {uid})"

        url = reverse("admin:auth_user_change", args=[uid])
        return format_html("<a href='{}'>View User</a>", url)

    user_link.short_description = "User Profile"

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