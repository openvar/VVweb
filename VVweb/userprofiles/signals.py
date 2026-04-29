# userprofiles/signals.py

from django.dispatch import receiver
from allauth.account.signals import user_signed_up, email_confirmed
from django.utils import timezone
from django.db.models.signals import post_save, post_init
from django.core.mail import send_mail
from django.conf import settings

from .models import UserProfile
from ..web.models import (
    InstitutionDomain,
    InstitutionMembership,
    VariantQuota,
)

from allauth.account.models import EmailAddress

import logging
logger = logging.getLogger(__name__)


# ======================================================================
# USER SIGN-UP → CREATE USER PROFILE
# ======================================================================
@receiver(user_signed_up)
def create_user_profile(request, user, **kwargs):
    profile, created = UserProfile.objects.get_or_create(user=user)
    if created:
        # Lowercase stored email immediately
        if user.email:
            lower = user.email.lower().strip()
            if user.email != lower:
                user.email = lower
                user.save(update_fields=["email"])
        logger.info(f"[user_signed_up] Created UserProfile for {user.username}")


# ======================================================================
# CAPTURE ORIGINAL PROFILE STATE
# ======================================================================
@receiver(post_init, sender=UserProfile)
def store_original_profile_state(sender, instance, **kwargs):
    instance._original_org_type = instance.org_type
    instance._original_verification_status = instance.verification_status


# ======================================================================
# QUOTA ENFORCEMENT
# ======================================================================
def enforce_commercial_quota(user, profile):
    is_commercial = (
        profile.org_type in ["commercial", "commercial_healthcare"]
        or profile.verification_status in ["commercial", "commercial_healthcare"]
    )

    quota, _ = VariantQuota.objects.get_or_create(user=user)

    if is_commercial:
        if quota.plan != "commercial":
            quota.plan = "commercial"
            quota.custom_limit = None
            quota.subscription_expires = None
            quota.count = 0
            quota.last_reset = timezone.now()
            quota.save()
            logger.info(f"[quota] Set plan=COMMERCIAL for {user.username}")
    else:
        if quota.plan == "commercial":
            quota.plan = "standard"
            quota.custom_limit = None
            quota.subscription_expires = None
            quota.save()
            logger.info(f"[quota] Set plan=STANDARD for {user.username}")


# ======================================================================
# PROFILE SAVE: COMMERCIAL EMAIL + BANNED EMAIL + QUOTA SYNC
# ======================================================================
@receiver(post_save, sender=UserProfile)
def enforce_status_transitions(sender, instance, **kwargs):
    user = instance.user
    profile = instance

    old_org = getattr(instance, "_original_org_type", None)
    old_status = getattr(instance, "_original_verification_status", None)

    new_org = profile.org_type
    new_status = profile.verification_status

    # Lowercase user.email on every save
    if user.email:
        lower = user.email.lower().strip()
        if user.email != lower:
            user.email = lower
            user.save(update_fields=["email"])

    # -------------------------------------------------------
    # COMMERCIAL EMAIL (transition-only)
    # -------------------------------------------------------
    became_commercial = (
        (old_org != "commercial" and new_org == "commercial")
        or (old_status != "commercial" and new_status == "commercial")
    )

    if became_commercial:
        logger.info(f"[email] Sending commercial activation email → {user.username}")

        send_mail(
            subject="VariantValidator – Commercial Access Required",
            message=(
                f"Hello {user.username},\n\n"
                "Your VariantValidator account is now set up — thank you for registering.\n\n"
                "We’ve recently updated our service model to ensure we can maintain the infrastructure, "
                "support continued development, and keep VariantValidator running reliably into the future.\n\n"
                "Based on the information provided, your account has been classified as *commercial use*. "
                "Commercial users require a paid licence to perform variant validations.\n\n"
                "• To request a manual trial allocation, or to have your account reviewed, please email admin@variantvalidator.org\n"
                "• Paid licensing options will be available soon:\n"
                "  https://variantvalidator.org/paid-options/   <-- placeholder link\n\n"
                "Until a licence or trial is applied to your account, your commercial quota is set to zero variants.\n\n"
                "Thank you for your interest in VariantValidator — your support helps us keep the service available "
                "for the wider community.\n"
                "— VariantValidator Team"
            ),
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@variantvalidator.org"),
            recipient_list=[user.email],
            fail_silently=True,
        )

    # -------------------------------------------------------
    # BANNED EMAIL (OPTION B — transition-only)
    # -------------------------------------------------------
    became_banned = (old_status != "banned" and new_status == "banned")

    if became_banned:
        logger.info(f"[email] Sending banned notification → {user.username}")

        send_mail(
            subject="VariantValidator – Account Deactivated",
            message=(
                f"Hello {user.username},\n\n"
                "Your VariantValidator account has been deactivated because we were unable to "
                "verify your identity or eligibility, or because activity was detected that "
                "does not comply with our terms of use.\n\n"
                "If you believe this was made in error or can provide additional information, please contact:\n"
                "admin@variantvalidator.org\n\n"
                "You may include:\n"
                " • an institutional or organisational email\n"
                " • ORCID, LinkedIn, or institutional profile links\n"
                " • your intended use of VariantValidator\n\n"
                "Thank you,\n"
                "— VariantValidator Team"
            ),
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@variantvalidator.org"),
            recipient_list=[user.email],
            fail_silently=True,
        )

    # Sync quotas (always after email logic)
    enforce_commercial_quota(user, profile)

    # Store updated originals
    instance._original_org_type = instance.org_type
    instance._original_verification_status = instance.verification_status


# ======================================================================
# EMAIL CONFIRMED → INSTITUTION SYNC (PRIMARY EMAIL ONLY)
# ======================================================================
@receiver(email_confirmed)
def handle_email_verified(sender, request, email_address, **kwargs):
    user = email_address.user
    profile, _ = UserProfile.objects.get_or_create(user=user)

    # ----------------------------------------------------------
    # ALWAYS store user.email in lowercase
    # ----------------------------------------------------------
    if user.email:
        lower = user.email.lower().strip()
        if user.email != lower:
            user.email = lower
            user.save(update_fields=["email"])

    # ----------------------------------------------------------
    # Mark profile email as verified
    # ----------------------------------------------------------
    profile.email_is_verified = True
    profile.completion_level = profile.get_completion_level()
    profile.save()

    # ----------------------------------------------------------
    # PRIMARY verified EmailAddress ONLY
    # ----------------------------------------------------------
    primary = EmailAddress.objects.filter(
        user=user,
        primary=True,
        verified=True
    ).first()

    if not primary:
        logger.info(f"[email_confirmed] No verified primary email for {user.username}")
        InstitutionMembership.objects.filter(user=user, active=True).update(active=False)
        VariantQuota.objects.filter(user=user).update(institution=None)
        enforce_commercial_quota(user, profile)
        return

    # Lowercase primary email too
    lower_ea = primary.email.lower().strip()
    if primary.email != lower_ea:
        primary.email = lower_ea
        primary.save(update_fields=["email"])

    # Extract domain
    try:
        domain = lower_ea.split("@", 1)[1]
    except Exception:
        domain = ""

    if not domain:
        logger.info(f"[email_confirmed] Invalid primary email → clearing membership for {user.username}")
        InstitutionMembership.objects.filter(user=user, active=True).update(active=False)
        VariantQuota.objects.filter(user=user).update(institution=None)
        enforce_commercial_quota(user, profile)
        return

    # ----------------------------------------------------------
    # MATCH using PRIMARY DOMAIN ONLY
    # ----------------------------------------------------------
    matches = []
    for inst_domain in InstitutionDomain.objects.select_related("institution"):
        suffix = inst_domain.domain
        if domain == suffix or domain.endswith("." + suffix):
            matches.append((inst_domain.institution, suffix))

    if not matches:
        logger.info(f"[email_confirmed] No institution match for {user.username} → domain={domain}")
        InstitutionMembership.objects.filter(user=user, active=True).update(active=False)
        VariantQuota.objects.filter(user=user).update(institution=None)
        enforce_commercial_quota(user, profile)
        return

    # Pick longest suffix
    matches.sort(key=lambda x: len(x[1]), reverse=True)
    best_institution, best_suffix = matches[0]

    # ----------------------------------------------------------
    # ACTIVATE CORRECT MEMBERSHIP
    # ----------------------------------------------------------
    membership, created = InstitutionMembership.objects.get_or_create(
        user=user,
        institution=best_institution,
        defaults={
            "source": "domain",
            "email_used": lower_ea,
            "verified_at": timezone.now(),
            "active": True,
        }
    )

    if not created:
        membership.active = True
        membership.email_used = lower_ea
        membership.verified_at = timezone.now()
        membership.save()

    # Deactivate others
    InstitutionMembership.objects.filter(
        user=user,
        active=True
    ).exclude(institution=best_institution).update(active=False)

    # ----------------------------------------------------------
    # UPDATE QUOTA INSTITUTION
    # ----------------------------------------------------------
    quota, _ = VariantQuota.objects.get_or_create(user=user)

    if quota.institution != best_institution:
        quota.institution = best_institution
        quota.save()
        logger.info(
            f"[email_confirmed] quota institution → {best_institution.name} (suffix={best_suffix})"
        )

    # ----------------------------------------------------------
    # ENFORCE commercial vs standard plan
    # ----------------------------------------------------------
    enforce_commercial_quota(user, profile)


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