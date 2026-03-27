from django.contrib import admin
from . import models
from django_celery_results.models import TaskResult


# Register your own models
admin.site.register(models.Contact)


# Custom Celery TaskResult admin to expose user_id in admin panel
@admin.register(TaskResult)
class TaskResultAdmin(admin.ModelAdmin):
    """
    Overrides the default django-celery-results admin display so we can see
    which authenticated user triggered each Celery task.
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
        Read the `user_id` from the task result's meta data.
        Meta is stored as JSON by django-celery-results.
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