# userprofiles/admin.py

from django.contrib import admin
from django.utils import timezone
from .models import UserProfile


@admin.action(description="Mark selected users as Verified (non-commercial)")
def mark_verified(modeladmin, request, queryset):
    queryset.update(
        verification_status="verified",
        verified_at=timezone.now(),
        verified_by=request.user,
    )


@admin.action(description="Mark selected users as Commercial")
def mark_commercial(modeladmin, request, queryset):
    queryset.update(verification_status="commercial")


@admin.action(description="Ban selected users")
def ban_users(modeladmin, request, queryset):
    queryset.update(verification_status="banned")


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "org_type",
        "verification_status",
        "country",
        "email_is_verified",
        "terms_accepted_at",
        "verified_at",
    )

    search_fields = ("user__username", "user__email", "institution")

    list_filter = ("org_type", "verification_status", "country")

    actions = [mark_verified, mark_commercial, ban_users]

    readonly_fields = (
        "verified_at",
        "verified_by",
        "terms_accepted_at",
        "rejection_reason",
    )

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