# userprofiles/admin.py

from django.contrib import admin
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings

from .models import UserProfile


# ============================================================
# EMAIL HELPER
# ============================================================

def notify_user(profile, subject, message):
    """
    Send a notification email to the user.
    In DEBUG, fail_silently=False so you see errors immediately.
    In production, fail_silently=True so admin actions don't crash.
    """
    send_mail(
        subject,
        message,
        getattr(settings, "DEFAULT_FROM_EMAIL", "dev-noreply@variantvalidator.local"),
        [profile.user.email],
        fail_silently=not settings.DEBUG,
    )


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

        # Notify user
        notify_user(
            profile,
            "Your VariantValidator account has been approved",
            (
                f"Hello {profile.user.username},\n\n"
                "Your VariantValidator account has now been approved.\n"
                "You may now use VariantValidator.\n\n"
                "Regards,\nVariantValidator Team"
            ),
        )


@admin.action(description="Mark selected users as Commercial")
def mark_commercial(modeladmin, request, queryset):
    for profile in queryset:
        profile.verification_status = "commercial"
        profile.save()

        # Notify user
        notify_user(
            profile,
            "VariantValidator – Commercial Access Required",
            (
                f"Hello {profile.user.username},\n\n"
                "Your account requires a commercial licence.\n"
                "Please visit the commercial page inside VariantValidator.\n\n"
                "Regards,\nVariantValidator Team"
            ),
        )


@admin.action(description="Ban selected users")
def ban_users(modeladmin, request, queryset):
    for profile in queryset:
        profile.verification_status = "banned"
        profile.save()

        # Notify user
        notify_user(
            profile,
            "VariantValidator – Access Suspended",
            (
                f"Hello {profile.user.username},\n\n"
                "Your VariantValidator account has been suspended or not approved.\n"
                "If you believe this is an error, contact support.\n\n"
                "Regards,\nVariantValidator Team"
            ),
        )


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

    def save_model(self, request, obj, form, change):
        """
        Auto-fill verified timestamps if the dropdown is used
        to set verification_status='verified'. Also sends the email notification.
        """
        if change and "verification_status" in form.changed_data:
            if obj.verification_status == "verified":
                if not obj.verified_at:
                    obj.verified_at = timezone.now()
                if not obj.verified_by:
                    obj.verified_by = request.user

                # Notify user when verified manually
                notify_user(
                    obj,
                    "Your VariantValidator account has been approved",
                    (
                        f"Hello {obj.user.username},\n\n"
                        "Your VariantValidator account has now been approved.\n"
                        "You may now use VariantValidator.\n\n"
                        "Regards,\nVariantValidator Team"
                    ),
                )

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