# userprofiles/admin.py

from django.contrib import admin
from django.utils import timezone
from .models import UserProfile


# ============================
# ADMIN ACTIONS
# ============================

@admin.action(description="Mark selected users as Verified (non-commercial)")
def mark_verified(modeladmin, request, queryset):
    now = timezone.now()
    for profile in queryset:
        profile.verification_status = "verified"
        profile.verified_at = now
        profile.verified_by = request.user
        profile.save()


@admin.action(description="Mark selected users as Commercial")
def mark_commercial(modeladmin, request, queryset):
    queryset.update(verification_status="commercial")


@admin.action(description="Ban selected users")
def ban_users(modeladmin, request, queryset):
    queryset.update(verification_status="banned")


# ============================
# MODEL ADMIN
# ============================

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "org_type",
        "verification_status",
        "email_is_verified",
        "terms_accepted_at",
        "verified_at",
    )

    search_fields = ("user__username", "user__email", "institution")

    list_filter = ("org_type", "verification_status", "country")

    actions = [
        mark_verified,
        mark_commercial,
        ban_users,
    ]

    readonly_fields = (
        "verified_at",
        "verified_by",
        "terms_accepted_at",
        "rejection_reason",
    )

    # Optional: Auto-timestamp verified_by/verified_at when using dropdown
    def save_model(self, request, obj, form, change):
        if "verification_status" in form.changed_data:
            if obj.verification_status == "verified":
                if obj.verified_at is None:
                    obj.verified_at = timezone.now()
                if obj.verified_by is None:
                    obj.verified_by = request.user
        super().save_model(request, obj, form, change)

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