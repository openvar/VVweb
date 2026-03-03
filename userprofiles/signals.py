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
# USER SIGN-UP → CREATE USER PROFILE
# ======================================================================
@receiver(user_signed_up)
def create_user_profile(request, user, **kwargs):
    """
    Create a UserProfile when a new user signs up.
    VariantQuota is created separately in web/signals.py.
    """
    profile, created = UserProfile.objects.get_or_create(user=user)
    if created:
        logger.info(f"[user_signed_up] Created UserProfile for {user.username}")
    else:
        logger.info(f"[user_signed_up] UserProfile already existed for {user.username}")


# ======================================================================
# CAPTURE ORIGINAL PROFILE STATE (NEEDED TO DETECT ADMIN TRANSITIONS)
# ======================================================================
@receiver(post_init, sender=UserProfile)
def store_original_profile_state(sender, instance, **kwargs):
    """
    Cache original values on instance so post_save can detect transitions.
    This solves the 'admin change detected after save' problem.
    """
    instance._original_org_type = instance.org_type
    instance._original_verification_status = instance.verification_status


# ======================================================================
# COMMERCIAL QUOTA ENFORCEMENT
# ======================================================================
def enforce_commercial_quota(user, profile):
    """
    Ensures VariantQuota accurately reflects commercial/non-commercial status.

    COMMERCIAL if:
        - org_type = commercial
        OR
        - verification_status = commercial

    NON-COMMERCIAL:
        - neither field indicates commercial
    """

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

            logger.info(
                f"[commercial_enforce] Set plan=COMMERCIAL for {user.username}"
            )
    else:
        # Downgrade only if previously commercial
        if quota.plan == "commercial":
            quota.plan = "standard"
            quota.custom_limit = None
            quota.subscription_expires = None
            quota.save()

            logger.info(
                f"[commercial_enforce] Downgraded {user.username} to STANDARD"
            )


# ======================================================================
# COMMERCIAL EMAIL + ENFORCEMENT ON PROFILE SAVE (ALL 4 WORKFLOWS)
# ======================================================================
@receiver(post_save, sender=UserProfile)
def enforce_commercial_on_profile_save(sender, instance, **kwargs):
    """
    Handles ALL required workflows:

    1. User declares org_type="commercial"
    2. Admin sets verification_status="commercial"
    3. System auto-verifies commercial via email-confirmed
    4. Admin changes user back → downgrade to standard

    Uses pre-save originals captured by post_init to detect transitions.
    """

    user = instance.user
    profile = instance

    # -------------------------------------------------------
    # Read original values cached by post_init
    # (if absent, treat as None)
    # -------------------------------------------------------
    old_org = getattr(instance, "_original_org_type", None)
    old_status = getattr(instance, "_original_verification_status", None)

    new_org = profile.org_type
    new_status = profile.verification_status

    # -------------------------------------------------------
    # Detect promotion to commercial (transition-only)
    # -------------------------------------------------------
    became_commercial = (
        (old_org != "commercial" and new_org == "commercial") or
        (old_status != "commercial" and new_status == "commercial")
    )

    # Send commercial email ONLY when transitioning into commercial
    # (Admin flip, system update, or user-declared if not already sent elsewhere)
    if became_commercial:
        logger.info(f"[commercial_email] Sending commercial activation email to {user.username}")

        send_mail(
            subject="VariantValidator – Commercial Access Required",
            message=(
                f"Hello {user.username},\n\n"
                "Your VariantValidator account has been classified as *commercial use*.\n\n"
                "Commercial users require a paid licence to perform variant validations.\n\n"
                "If you would like to request a manual trial allocation, please email:\n"
                "admin@variantvalidator.org\n\n"
                "Paid licensing options will be available soon.\n\n"
                "Thank you for supporting VariantValidator — your contributions help keep the service available "
                "for the global genomics community.\n\n"
                "— VariantValidator Team"
            ),
            from_email=getattr(settings, "DEFAULT_FROM_EMAIL", "noreply@variantvalidator.org"),
            recipient_list=[user.email],
            fail_silently=True,
        )

    # -------------------------------------------------------
    # Enforce quota after email logic
    # -------------------------------------------------------
    enforce_commercial_quota(user, profile)

    # -------------------------------------------------------
    # Update cached originals so subsequent saves compare correctly
    # -------------------------------------------------------
    instance._original_org_type = instance.org_type
    instance._original_verification_status = instance.verification_status


# ======================================================================
# EMAIL CONFIRMED → INSTITUTION SYNC + COMMERCIAL ENFORCEMENT
# ======================================================================
@receiver(email_confirmed)
def handle_email_verified(sender, request, email_address, **kwargs):
    """
    When a user verifies email:
      - Mark profile email verified
      - Compute completion %
      - Compute institutional membership
      - Update VariantQuota institution link
      - Enforce commercial logic (auto/commercial users)
    """

    user = email_address.user
    logger.info(f"[email_confirmed] Fired for user={user.username} email={email_address.email}")

    # ---------------------------
    # 1. Profile update
    # ---------------------------
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.email_is_verified = True
    profile.completion_level = profile.get_completion_level()
    profile.save()

    # ---------------------------
    # 2. Verified domains
    # ---------------------------
    verified_emails = EmailAddress.objects.filter(user=user, verified=True)
    verified_domains = []

    for e in verified_emails:
        try:
            dom = e.email.split("@", 1)[1].lower().strip()
            if dom:
                verified_domains.append(dom)
        except Exception:
            continue

    if not verified_domains:
        InstitutionMembership.objects.filter(user=user, active=True).update(active=False)
        VariantQuota.objects.filter(user=user).update(institution=None)

        enforce_commercial_quota(user, profile)
        return

    # ---------------------------
    # 3. Institution matching
    # ---------------------------
    matches = []

    for inst_domain in InstitutionDomain.objects.select_related("institution"):
        inst_suffix = inst_domain.domain
        for d in verified_domains:
            if d == inst_suffix or d.endswith("." + inst_suffix):
                matches.append((inst_domain.institution, inst_suffix))

    if not matches:
        InstitutionMembership.objects.filter(user=user, active=True).update(active=False)
        VariantQuota.objects.filter(user=user).update(institution=None)

        enforce_commercial_quota(user, profile)
        return

    # ---------------------------
    # 4. Best match
    # ---------------------------
    matches.sort(key=lambda x: len(x[1]), reverse=True)
    best_institution, best_domain = matches[0]

    # ---------------------------
    # 5. Create/update membership
    # ---------------------------
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

    # ---------------------------
    # 6. Deactivate other memberships
    # ---------------------------
    InstitutionMembership.objects.filter(
        user=user,
        active=True
    ).exclude(institution=best_institution).update(active=False)

    # ---------------------------
    # 7. Update quota institution pointer
    # ---------------------------
    try:
        quota = VariantQuota.objects.get(user=user)
    except VariantQuota.DoesNotExist:
        quota = VariantQuota.objects.create(user=user)

    if quota.institution != best_institution:
        quota.institution = best_institution
        quota.save()

    # ---------------------------
    # 8. Commercial enforcement (auto/commercial)
    # ---------------------------
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