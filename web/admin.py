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
# Custom TaskResult admin with user_id and richer result display
# -------------------------------------------------------------------
@admin.register(TaskResult)
class TaskResultAdmin(DefaultTaskResultAdmin):
    """
    Overrides the default django-celery-results admin to add user_id display
    from the return payload (preferred) or legacy meta (fallback).
    """

    list_display = (
        "task_id",
        "status",
        "date_done",
        "get_user_id",
        "get_email",
        "get_variant",
    )

    search_fields = ("task_id", "status", "result", "meta")
    list_filter = ("status", "date_done")

    # ----------------------------
    # Extract user_id
    # ----------------------------
    def get_user_id(self, obj):
        # Prefer new-style user_id in result JSON
        if isinstance(obj.result, dict) and "user_id" in obj.result:
            return obj.result["user_id"]

        # Fallback for historical tasks
        if isinstance(obj.meta, dict) and "user_id" in obj.meta:
            return obj.meta["user_id"]

        return "-"

    get_user_id.short_description = "User ID"

    # ----------------------------
    # Extract email
    # ----------------------------
    def get_email(self, obj):
        if isinstance(obj.result, dict):
            return obj.result.get("email", "-")
        return "-"

    get_email.short_description = "Email"

    # ----------------------------
    # Extract variant
    # ----------------------------
    def get_variant(self, obj):
        if isinstance(obj.result, dict):
            return obj.result.get("variant", "-")
        return "-"

    get_variant.short_description = "Variant"


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
