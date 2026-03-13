# userprofiles/admin.py

from django.contrib import admin, messages
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings

from allauth.account.models import EmailAddress
from datetime import timedelta

from .models import UserProfile


# ======================================================================
# EMAIL UTIL
# ======================================================================

def notify_user(profile, subject, message):
    """
    Send a notification email to a user.
    fail_silently = not DEBUG → admin UI never breaks on email failure.
    """
    send_mail(
        subject,
        message,
        getattr(settings, "DEFAULT_FROM_EMAIL", "dev-noreply@variantvalidator.local"),
        [profile.user.email],
        fail_silently=not settings.DEBUG,
    )


# ======================================================================
# PRIMARY EMAIL HELPERS
# ======================================================================

def get_primary_email(user):
    """Return lowercase primary email or None."""
    try:
        ea = EmailAddress.objects.filter(user=user, primary=True).first()
        if ea:
            return ea.email.lower().strip()
    except Exception:
        pass
    return None


def primary_email_domain(user):
    """Extract domain from primary email."""
    email = get_primary_email(user)
    if email and "@" in email:
        return email.split("@", 1)[1]
    return "-"


def get_institution_name(user):
    """Show user's institution based on VariantQuota pointer."""
    try:
        quota = user.variant_quota
        if quota.institution:
            return quota.institution.name
    except Exception:
        pass
    return "-"


def get_effective_allowance(user):
    """Return effective allowance for display in admin."""
    try:
        quota = user.variant_quota
        return quota.effective_allowance
    except Exception:
        return "-"


# ======================================================================
# ADMIN ACTIONS: VERIFIED / COMMERCIAL / BANNED
# ======================================================================

@admin.action(description="Mark selected users as Verified (non-commercial)")
def mark_verified(modeladmin, request, queryset):

    now = timezone.now()

    for profile in queryset:
        user = profile.user

        # Normalise email
        if user.email:
            lower = user.email.lower().strip()
            if user.email != lower:
                user.email = lower
                user.save(update_fields=["email"])

        # Apply verified status
        profile.verification_status = "verified"
        profile.verified_at = now
        profile.verified_by = request.user
        profile.save()

        subject = "Your VariantValidator account has been approved"
        message = (
            f"Hello {user.username},\n\n"
            "Your VariantValidator account is now set up and ready to use — thank you for joining us.\n\n"
            "VariantValidator is a community resource... (message unchanged)\n\n"
            "— VariantValidator Team"
        )

        notify_user(profile, subject, message)

        # Trigger quota update (signal handles institution logic)
        try:
            quota = user.variant_quota
            quota.save()  # triggers recalculation
        except Exception:
            pass


@admin.action(description="Mark selected users as Commercial")
def mark_commercial(modeladmin, request, queryset):

    for profile in queryset:
        user = profile.user

        if user.email:
            lower = user.email.lower().strip()
            if user.email != lower:
                user.email = lower
                user.save(update_fields=["email"])

        # Apply commercial status
        profile.verification_status = "commercial"
        profile.save()

        subject = "VariantValidator – Commercial Access Required"
        message = (
            f"Hello {user.username},\n\n"
            "Your VariantValidator account has been classified as *commercial use*.\n\n"
            "Commercial users require a paid licence... (message unchanged)\n\n"
            "— VariantValidator Team"
        )

        notify_user(profile, subject, message)

        # Trigger quota recalculation
        try:
            quota = user.variant_quota
            quota.save()
        except Exception:
            pass


@admin.action(description="Ban selected users")
def ban_users(modeladmin, request, queryset):

    for profile in queryset:
        user = profile.user

        if user.email:
            lower = user.email.lower().strip()
            if user.email != lower:
                user.email = lower
                user.save(update_fields=["email"])

        profile.verification_status = "banned"
        profile.save()

        subject = "VariantValidator – Access Suspended"
        message = (
            f"Hello {user.username},\n\n"
            "Your VariantValidator account has been suspended or could not be approved.\n"
            "If you believe this is an error, please contact support.\n\n"
            "— VariantValidator Team"
        )

        notify_user(profile, subject, message)

        # Force quota update
        try:
            quota = user.variant_quota
            quota.save()
        except Exception:
            pass


# ======================================================================
# NEW ADMIN ACTION: FORCE RE‑VALIDATION (CORRECTED)
# ======================================================================


@admin.action(description="Force re-validation for selected users (reset to NEW)")
def force_revalidation(modeladmin, request, queryset):
    """
    Reset selected users to an exact 'new account' state so middleware treats
    them as NEW (not 'expired') on the very next request.

      • terms_accepted_at = None       <-- critical to avoid 'stuck expired'
      • email_is_verified = False
      • verification_status = 'not_started'
      • org_type = None, jobrole = "", personal_info_is_completed = False
      • completion_level = 0, verified_at/by = None, rejection_reason = ""
      • Allauth EmailAddress: ensure row exists, primary=True, verified=False
    """
    updated = 0

    for profile in queryset.select_related("user"):
        user = profile.user

        # Normalize Django User email
        if user.email:
            lower = user.email.lower().strip()
            if user.email != lower:
                user.email = lower
                user.save(update_fields=["email"])

        # ---- Profile -> NEW account state
        profile.email_is_verified = False
        profile.verification_status = "not_started"
        profile.org_type = None
        profile.jobrole = ""
        profile.personal_info_is_completed = False
        profile.completion_level = 0
        profile.verified_at = None
        profile.verified_by = None
        profile.rejection_reason = ""
        profile.terms_accepted_at = None   # <-- treat as NEW after reset (prevents "stuck expired")
        profile.save()

        # ---- Allauth email rows
        if user.email:
            # ensure the row for user.email exists
            email_obj, _ = EmailAddress.objects.get_or_create(
                user=user,
                email=user.email,
                defaults={"primary": True, "verified": False},
            )
            # unverify and make this the sole primary
            email_obj.verified = False
            email_obj.primary = True
            email_obj.save(update_fields=["verified", "primary"])
            EmailAddress.objects.filter(user=user).exclude(pk=email_obj.pk).update(primary=False)

        updated += 1

    modeladmin.message_user(
        request,
        f"Forced re‑validation for {updated} profile(s): reset to NEW (terms cleared, email unverified).",
        level=messages.SUCCESS,
    )


# ======================================================================
# USERPROFILE ADMIN
# ======================================================================

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):

    list_display = (
        "user",
        "org_type",
        "verification_status",
        "email_is_verified",
        "primary_email",
        "primary_domain",
        "institution_name",
        "effective_allowance_display",
        "terms_accepted_at",
        "verified_at",
    )

    search_fields = ("user__username", "user__email", "country", "org_type")
    list_filter = ("org_type", "verification_status", "country")

    # TERMS ACCEPTED REMAINS READ-ONLY (your requirement)
    readonly_fields = (
        "verified_at",
        "verified_by",
        "terms_accepted_at",
        "rejection_reason",
    )

    actions = [
        mark_verified,
        mark_commercial,
        ban_users,
        force_revalidation,
    ]

    def primary_email(self, obj):
        return get_primary_email(obj.user)
    primary_email.short_description = "Primary Email"

    def primary_domain(self, obj):
        return primary_email_domain(obj.user)
    primary_domain.short_description = "Domain"

    def institution_name(self, obj):
        return get_institution_name(obj.user)
    institution_name.short_description = "Institution"

    def effective_allowance_display(self, obj):
        return get_effective_allowance(obj.user)
    effective_allowance_display.short_description = "Eff. Allowance"

    # -------------------------
    # Auto-normalize email & trigger messages
    # -------------------------
    def save_model(self, request, obj, form, change):
        user = obj.user

        if user.email:
            lower = user.email.lower().strip()
            if lower != user.email:
                user.email = lower
                user.save(update_fields=["email"])

        changed = getattr(form, "changed_data", [])
        if change and "verification_status" in changed:
            if obj.verification_status == "verified":
                if not obj.verified_at:
                    obj.verified_at = timezone.now()
                if not obj.verified_by:
                    obj.verified_by = request.user

                subject = "Your VariantValidator account has been approved"
                message = (
                    f"Hello {obj.user.username},\n\n"
                    "Your VariantValidator account is now set up and ready to use...\n\n"
                    "— VariantValidator Team"
                )
                notify_user(obj, subject, message)

        super().save_model(request, obj, form, change)

        try:
            quota = user.variant_quota
            quota.save()
        except Exception:
            pass


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