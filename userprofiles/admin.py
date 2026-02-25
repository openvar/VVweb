# userprofiles/admin.py

from django.contrib import admin
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings

from .models import UserProfile


# ==========================================================
# EMAIL HELPERS
# ==========================================================

def send_user_email(user, subject, message):
    """Send a notification email to the user."""
    send_mail(
        subject=subject,
        message=message,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@variantvalidator.org"),
        recipient_list=[user.email],
        fail_silently=True,
    )


# ==========================================================
# ADMIN ACTIONS
# ==========================================================

@admin.action(description="Mark selected users as Verified (non-commercial)")
def mark_verified(modeladmin, request, queryset):
    now = timezone.now()
    for profile in queryset:
        profile.verification_status = "verified"
        profile.verified_at = now
        profile.verified_by = request.user
        profile.save()

        # Notify the user
        send_user_email(
            profile.user,
            "Your VariantValidator account has been approved",
            (
                f"Hello {profile.user.username},\n\n"
                "Your VariantValidator account has now been verified.\n"
                "You may use the service immediately.\n\n"
                "Thank you,\nVariantValidator Team"
            ),
        )


@admin.action(description="Mark selected users as Commercial")
def mark_commercial(modeladmin, request, queryset):
    for profile in queryset:
        profile.verification_status = "commercial"
        profile.save()

        # Notify the user
        send_user_email(
            profile.user,
            "VariantValidator Commercial Access Required",
            (
                f"Hello {profile.user.username},\n\n"
                "Your account has been reviewed and requires a commercial licence.\n"
                "Please visit the commercial page within VariantValidator to continue.\n\n"
                "Thank you,\nVariantValidator Team"
            ),
        )


@admin.action(description="Ban selected users (reject / suspend)")
def ban_users(modeladmin, request, queryset):
    for profile in queryset:
        profile.verification_status = "banned"
        profile.save()

        # Notify the user
        send_user_email(
            profile.user,
            "Your VariantValidator account could not be approved",
            (
                f"Hello {profile.user.username},\n\n"
                "Your verification request could not be approved or your access has been suspended.\n"
                "If you believe this is in error, please contact support.\n\n"
                "Thank you,\nVariantValidator Team"
            ),
        )


# ==========================================================
# MODEL ADMIN
# ==========================================================

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
        Automatically fill verified_at / verified_by if admin manually
        changes verification_status to 'verified'.
        """
        if change and "verification_status" in form.changed_data:
            if obj.verification_status == "verified":
                if not obj.verified_at:
                    obj.verified_at = timezone.now()
                if not obj.verified_by:
                    obj.verified_by = request.user

                # Email user about approval
                send_user_email(
                    obj.user,
                    "Your VariantValidator account has been approved",
                    (
                        f"Hello {obj.user.username},\n\n"
                        "Your VariantValidator account has now been verified.\n"
                        "You may now use the service.\n\n"
                        "Thank you,\nVariantValidator Team"
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