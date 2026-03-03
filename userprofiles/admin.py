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
    In DEBUG, fail_silently=False so email errors surface.
    In production (DEBUG=False), fail quietly so admin UI isn't interrupted.
    """
    send_mail(
        subject,
        message,
        getattr(settings, "DEFAULT_FROM_EMAIL", "dev-noreply@variantvalidator.local"),
        [profile.user.email],
        fail_silently=not settings.DEBUG,
    )


# ============================================================
# ADMIN ACTIONS
# ============================================================

@admin.action(description="Mark selected users as Verified (non-commercial)")
def mark_verified(modeladmin, request, queryset):
    """
    Approve non-commercial users (research, healthcare, charity, government).
    Sends a friendly sustainability message encouraging subscription support
    and institutional licences.
    """
    now = timezone.now()
    for profile in queryset:
        profile.verification_status = "verified"
        profile.verified_at = now
        profile.verified_by = request.user
        profile.save()

        # FRIENDLY COMMUNITY MESSAGE
        subject = "Your VariantValidator account has been approved"
        message = (
            f"Hello {profile.user.username},\n\n"
            "Your VariantValidator account is now set up and ready to use — thank you for joining us.\n\n"
            "VariantValidator is a community resource, and unlike many tools in this space, "
            "we do not receive academic, institutional, or external grant funding. Maintaining the "
            "infrastructure, supporting users, and improving the service is something we fund ourselves.\n\n"
            "If you ever require a higher monthly variant quota, or can support our efforts to keep VariantValidator free to our global community,  please consider purchasing a subscription. "
            "Your support directly helps us ensure VariantValidator remains reliable, available, and sustainable "
            "for the global community that depends on it.\n\n"
            "If you're part of publicly funded healthcare, a clinical laboratory, or a research organisation "
            "with multiple users, we encourage your organisation to contact us at admin@variantvalidator.org "
            "to discuss an institutional licence.\n\n"
            "• Paid licensing options will be available soon. A purchase link will appear here once the "
            "subscription portal is live:\n"
            "  https://variantvalidator.org/paid-options/   <-- placeholder link\n\n"
            "Thanks again for using VariantValidator — we hope it supports your work.\n\n"
            "— VariantValidator Team"
        )

        notify_user(profile, subject, message)


@admin.action(description="Mark selected users as Commercial")
def mark_commercial(modeladmin, request, queryset):
    """
    Classify users as commercial. Sends a professional message explaining
    the sustainability model, manual trial process, and future paid options.
    """
    for profile in queryset:
        profile.verification_status = "commercial"
        profile.save()

        subject = "VariantValidator – Commercial Access Required"
        message = (
            f"Hello {profile.user.username},\n\n"
            "Your VariantValidator account is now set up — thank you for registering.\n\n"
            "We’ve recently updated our service model to ensure we can maintain the infrastructure, "
            "support continued development, and keep VariantValidator running reliably into the future.\n\n"
            "Based on the information provided, your account has been classified as *commercial use*. "
            "Commercial users require a paid licence to perform variant validations.\n\n"
            "• If you would like to evaluate VariantValidator before committing, please email "
            "admin@variantvalidator.org to request a manual trial allocation.\n"
            "• Paid licensing options will be available soon. A purchase link will appear here once the "
            "subscription portal is live:\n"
            "  https://variantvalidator.org/paid-options/   <-- placeholder link\n\n"
            "Until a licence or trial is applied to your account, your commercial quota is set to "
            "zero variants per month.\n\n"
            "Thank you for your interest in VariantValidator — your support helps us keep the service "
            "available for the wider community.\n"
            "— VariantValidator Team"
        )

        notify_user(profile, subject, message)


@admin.action(description="Ban selected users")
def ban_users(modeladmin, request, queryset):
    for profile in queryset:
        profile.verification_status = "banned"
        profile.save()

        subject = "VariantValidator – Access Suspended"
        message = (
            f"Hello {profile.user.username},\n\n"
            "Your VariantValidator account has been suspended or could not be approved.\n"
            "If you believe this is an error, please contact support.\n\n"
            "— VariantValidator Team"
        )

        notify_user(profile, subject, message)


# ============================================================
# MODEL ADMIN
# ============================================================

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
        If an admin manually changes verification_status to 'verified',
        fill timestamps and send the same friendly non-commercial message.
        """
        if change and "verification_status" in getattr(form, "changed_data", []):
            if obj.verification_status == "verified":
                if not obj.verified_at:
                    obj.verified_at = timezone.now()
                if not obj.verified_by:
                    obj.verified_by = request.user
                obj.save(update_fields=["verified_at", "verified_by"])

                subject = "Your VariantValidator account has been approved"
                message = (
                    f"Hello {obj.user.username},\n\n"
                    "Your VariantValidator account is now set up and ready to use — thank you for joining us.\n\n"
                    "VariantValidator is a community resource, and unlike many tools in this space, "
                    "we do not receive academic, institutional, or external grant funding. Maintaining the "
                    "infrastructure, supporting users, and improving the service is something we fund ourselves.\n\n"
                    "If you ever require a higher monthly variant quota, or can support our efforts to keep VariantValidator free to our global community,  please consider purchasing a subscription. "
                    "Your support directly helps us ensure VariantValidator remains reliable, available, and sustainable "
                    "for the global community that depends on it.\n\n"
                    "If you're part of publicly funded healthcare, a clinical laboratory, or a research organisation "
                    "with multiple users, we encourage your organisation to contact us at admin@variantvalidator.org "
                    "to discuss an institutional licence.\n\n"
                    "Thanks again for using VariantValidator — we hope it supports your work.\n\n"
                    "— VariantValidator Team"
                )

                notify_user(obj, subject, message)

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