# userprofiles/admin.py

from django.contrib import admin, messages
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings

from allauth.account.models import EmailAddress

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
# SHARED VERIFIED EMAIL BUILDER (Single Source of Truth)
# ======================================================================

def build_verified_welcome_email(user):
    """Return the full verified-user onboarding email text."""
    allowance = getattr(settings, 'DEFAULT_MONTHLY_VARIANT_ALLOWANCE', '0')

    return (
        f"Hello {user.username},\n\n"
        "Your VariantValidator account is now set up and ready to use — thank you for joining us.\n\n"

        "VariantValidator is a community resource designed to support accurate variant interpretation,\n"
        "improve clinical reporting, and help researchers work to internationally agreed standards.\n"
        "Your verified account allows you to access the full set of tools.\n\n"

        f"As a verified non‑commercial user, you now have access to the standard allocation supported by our\n"
        f"academic and community‑driven infrastructure, which is {allowance} validations per month.\n"
        "If your needs exceed this allowance you will need to purchase a monthly subscription (link to subscription page),\n"
        "or if you are part of a wider clinical or institutional project, please contact us — we are happy to\n"
        "discuss institutional subscriptions to support your work.\n\n"

        "VariantValidator is offered as an open community resource, and unlike many scientific platforms,\n"
        "we do not receive external funding. Our global user community depends on us for accurate,\n"
        "standards‑compliant representation of variant data, and we strongly believe in providing equitable\n"
        "access as part of our social responsibility.\n\n"

        "As VariantValidator has grown into a widely used global genomics service, we have introduced a\n"
        "sustainability‑focused model to help ensure the infrastructure, maintenance, and development work\n"
        "required to keep the service reliable and available long‑term.\n"
        "You can read more about this approach here:\n"
        "https://www.uominnovationfactory.com/projects/supporting-variantvalidator-sustaining-a-global-genomics-service/\n\n"

        "In 2025, more than 200,000 users relied on VariantValidator worldwide. To keep the service running\n"
        "and available to all — and to maintain or develop the tools you depend on — please consider\n"
        "supporting us by purchasing a one‑month subscription. This is not about generating profit; it is\n"
        "about sustaining the infrastructure, ensuring reliability, and enabling continued development of\n"
        "resources for you and the wider community.\n\n"

        "If you have ideas, feature requests, or if you identify any bugs, please let us know. Your feedback\n"
        "directly shapes our development priorities and helps us continue improving this community resource.\n\n"

        "— VariantValidator Team"
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
        message = build_verified_welcome_email(user)

        notify_user(profile, subject, message)

        # Trigger quota update
        try:
            quota = user.variant_quota
            quota.save()
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

        profile.verification_status = "commercial"
        profile.save()

        subject = "VariantValidator – Commercial Access Required"
        message = (
            f"Hello {user.username},\n\n"
            "Your VariantValidator account is set up — thank you for registering.\n\n"

            "VariantValidator has introduced a sustainability‑focused service model to help sustain the platform as a widely used\n"
            "global genomics resource, ensuring we can continue maintaining the infrastructure, supporting users, and keeping\n"
            "the service running reliably for the community.\n\n"

            "You can read more about this approach here:\n"
            "https://www.uominnovationfactory.com/projects/supporting-variantvalidator-sustaining-a-global-genomics-service/\n\n"

            "Based on the information provided during registration, your account has been classified as\n"
            "commercial use. Commercial users require a valid licence to run variant validations.\n\n"

            "If you have not yet done so, you may activate a one‑time free evaluation month by logging in and clicking the button provided.\n"
            "This provides the same validation allowance as our free‑tier monthly quota and is intended to help you assess\n"
            "whether VariantValidator meets your needs.\n\n"

            "After your trial, or if you require additional capacity, please contact us for licensing or subscription options.\n"
            "These changes help ensure VariantValidator remains available, maintained, and reliable for all users.\n\n"

            "For assistance, subscription information, or trial enquiries, please contact:\n"
            "admin@variantvalidator.org\n\n"

            "Thank you for supporting the project.\n\n"
            "— VariantValidator Team"
        )

        notify_user(profile, subject, message)

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

        subject = "VariantValidator – Access Deactivated"
        message = (
            f"Hello {user.username},\n\n"
            "Your VariantValidator account has been deactivated.\n\n"

            "VariantValidator is a widely used global genomics service, and we have a responsibility to ensure\n"
            "that access is granted appropriately and in line with our terms of use. This is essential to\n"
            "maintaining the integrity, sustainability, and reliability of the service for the wider community.\n\n"

            "This action was taken because we were unable to verify your identity or eligibility, or because\n"
            "activity was detected that does not comply with our terms of use. As a result, your access has been\n"
            "restricted and you will be unable to use VariantValidator until the issue is resolved.\n\n"

            "You can read more about how we sustain and protect VariantValidator as a shared resource here:\n"
            "https://www.uominnovationfactory.com/projects/supporting-variantvalidator-sustaining-a-global-genomics-service/\n\n"

            "If you believe this decision was made in error, or you can provide additional information to\n"
            "support your eligibility, please contact us. When getting in touch, you may include:\n"
            " • An institutional or organisational email address\n"
            " • ORCID, LinkedIn, or institutional profile links\n"
            " • Details regarding your intended use of VariantValidator\n\n"

            "For assistance, please email:\n"
            "admin@variantvalidator.org\n\n"

            "Thank you for your cooperation.\n\n"
            "— VariantValidator Team"
        )

        notify_user(profile, subject, message)

        try:
            quota = user.variant_quota
            quota.save()
        except Exception:
            pass


# ======================================================================
# ADMIN ACTION: FORCE RE‑VALIDATION
# ======================================================================

@admin.action(description="Force re‑validation (reset to NEW) for selected users")
def force_revalidation(modeladmin, request, queryset):

    updated = 0
    now = timezone.now()

    for profile in queryset.select_related("user"):
        user = profile.user

        if user.email:
            lower = user.email.lower().strip()
            if user.email != lower:
                user.email = lower
                user.save(update_fields=["email"])

        profile.email_is_verified = False
        profile.verification_status = "not_started"
        profile.org_type = None
        profile.jobrole = ""
        profile.personal_info_is_completed = False
        profile.completion_level = 0
        profile.verified_at = None
        profile.verified_by = None
        profile.rejection_reason = ""
        profile.terms_accepted_at = None
        profile.reset_reason = "admin"
        profile.reset_at = now

        profile.save(update_fields=[
            "email_is_verified", "verification_status", "org_type", "jobrole",
            "personal_info_is_completed", "completion_level",
            "verified_at", "verified_by", "rejection_reason",
            "terms_accepted_at", "reset_reason", "reset_at",
        ])

        if user.email:
            email_obj, _ = EmailAddress.objects.get_or_create(
                user=user,
                email=user.email,
                defaults={"primary": True, "verified": False},
            )
            EmailAddress.objects.filter(user=user).exclude(pk=email_obj.pk).update(primary=False)
            if not email_obj.primary:
                email_obj.primary = True
            email_obj.verified = False
            email_obj.save(update_fields=["primary", "verified"])

        updated += 1

    modeladmin.message_user(
        request,
        f"Forced re‑validation for {updated} profile(s): reset to NEW.",
        level=messages.SUCCESS,
    )



# ======================================================================
# USERPROFILE ADMIN
# ======================================================================

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):

    list_display = (
        "user", "org_type", "verification_status", "email_is_verified",
        "primary_email", "primary_domain", "institution_name",
        "effective_allowance_display", "terms_accepted_at",
        "reset_reason", "reset_at", "verified_at",
    )

    search_fields = ("user__username", "user__email", "country", "org_type")
    list_filter = ("org_type", "verification_status", "country", "reset_reason")

    readonly_fields = (
        "verified_at", "verified_by", "terms_accepted_at",
        "rejection_reason", "reset_reason", "reset_at",
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

    def save_model(self, request, obj, form, change):
        user = obj.user

        if user.email:
            lower = user.email.lower().strip()
            if user.email != lower:
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
                message = build_verified_welcome_email(obj.user)
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