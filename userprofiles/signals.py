# userprofiles/signals.py

from django.dispatch import receiver
from allauth.account.signals import user_signed_up, email_confirmed
from django.utils import timezone
from django.db.models.signals import post_save, post_init
from django.core.mail import send_mail
from django.conf import settings

from .models import UserProfile
from web.models import (
    InstitutionDomain,
    InstitutionMembership,
    VariantQuota,
)

from allauth.account.models import EmailAddress

import logging
logger = logging.getLogger('vv')


# ======================================================================
# USER PROFILE SETUP
# ======================================================================
@receiver(user_signed_up)
def create_user_profile(request, user, **kwargs):
    profile, created = UserProfile.objects.get_or_create(user=user)
    if created:
        logger.info(f"[user_signed_up] Created UserProfile for {user.username}")


@receiver(post_init, sender=UserProfile)
def store_original_profile_state(sender, instance, **kwargs):
    instance._original_org_type = instance.org_type
    instance._original_verification_status = instance.verification_status


# ======================================================================
# QUOTA ENFORCEMENT
# ======================================================================
def enforce_commercial_quota(user, profile):
    is_commercial = (
        profile.org_type == "commercial"
        or profile.verification_status == "commercial"
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
# PROFILE SAVE → COMMERCIAL + BANNED EMAILS + QUOTA SYNC
# ======================================================================
@receiver(post_save, sender=UserProfile)
def enforce_status_transitions(sender, instance, **kwargs):
    user = instance.user
    profile = instance

    old_org = getattr(instance, "_original_org_type", None)
    old_status = getattr(instance, "_original_verification_status", None)

    new_org = profile.org_type
    new_status = profile.verification_status

    # -------------------------
    # Commercial transition
    # -------------------------
    became_commercial = (
        (old_org != "commercial" and new_org == "commercial") or
        (old_status != "commercial" and new_status == "commercial")
    )

    if became_commercial:
        send_mail(
            subject="VariantValidator – Commercial Access Required",
            message=(
                f"Hello {user.username},\n\n"
                "Your VariantValidator account has been classified as *commercial use*.\n\n"
                "Commercial users require a paid licence to perform variant validations.\n\n"
                "If you would like to request a manual trial allocation, please email:\n"
                "admin@variantvalidator.org\n\n"
                "Paid licensing options will be available soon.\n\n"
                "Thank you,\n"
                "— VariantValidator Team"
            ),
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@variantvalidator.org"),
            recipient_list=[user.email],
            fail_silently=True,
        )
        logger.info(f"[email] Commercial notification sent → {user.username}")

    # -------------------------
    # Banned transition (Option B)
    # -------------------------
    became_banned = (old_status != "banned" and new_status == "banned")

    if became_banned:
        send_mail(
            subject="VariantValidator – Account Deactivated",
            message=(
                f"Hello {user.username},\n\n"
                "Your VariantValidator account has been deactivated because we were unable "
                "to verify your identity or eligibility, or because activity was detected "
                "that does not comply with our terms of use.\n\n"
                "If you believe this decision was made in error or wish to provide additional information, "
                "please contact:\n"
                "admin@variantvalidator.org\n\n"
                "You may include:\n"
                " • an institutional or organisational email address\n"
                " • ORCID, LinkedIn or institutional profile links\n"
                " • details regarding your intended use of VariantValidator\n\n"
                "Thank you,\n"
                "— VariantValidator Team"
            ),
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@variantvalidator.org"),
            recipient_list=[user.email],
            fail_silently=True,
        )
        logger.info(f"[email] Banned notification sent → {user.username}")

    # Sync quota after email logic
    enforce_commercial_quota(user, profile)

    # Update stored originals
    instance._original_org_type = instance.org_type
    instance._original_verification_status = instance.verification_status


# ======================================================================
# EMAIL CONFIRMED → SYNC INSTITUTION + QUOTA
# ======================================================================
@receiver(email_confirmed)
def handle_email_verified(sender, request, email_address, **kwargs):
    user = email_address.user
    profile, _ = UserProfile.objects.get_or_create(user=user)

    profile.email_is_verified = True
    profile.completion_level = profile.get_completion_level()
    profile.save()

    verified_emails = EmailAddress.objects.filter(user=user, verified=True)
    verified_domains = []

    for e in verified_emails:
        try:
            dom = e.email.split("@")[1].lower().strip()
            verified_domains.append(dom)
        except:
            pass

    if not verified_domains:
        InstitutionMembership.objects.filter(user=user, active=True).update(active=False)
        VariantQuota.objects.filter(user=user).update(institution=None)
        enforce_commercial_quota(user, profile)
        return

    # Match institutions
    matches = []
    for inst_domain in InstitutionDomain.objects.select_related("institution"):
        suffix = inst_domain.domain
        for d in verified_domains:
            if d == suffix or d.endswith("." + suffix):
                matches.append((inst_domain.institution, suffix))

    if not matches:
        InstitutionMembership.objects.filter(user=user, active=True).update(active=False)
        VariantQuota.objects.filter(user=user).update(institution=None)
        enforce_commercial_quota(user, profile)
        return

    matches.sort(key=lambda x: len(x[1]), reverse=True)
    best_institution, best_domain = matches[0]

    membership, created = InstitutionMembership.objects.get_or_create(
        user=user,
        institution=best_institution,
        defaults={
            "source": "domain",
            "email_used": email_address.email,
            "verified_at": timezone.now(),
            "active": True,
        }
    )

    if not created:
        membership.active = True
        membership.email_used = email_address.email
        membership.verified_at = timezone.now()
        membership.save()

    InstitutionMembership.objects.filter(
        user=user,
        active=True
    ).exclude(institution=best_institution).update(active=False)

    quota, _ = VariantQuota.objects.get_or_create(user=user)

    if quota.institution != best_institution:
        quota.institution = best_institution
        quota.save()

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