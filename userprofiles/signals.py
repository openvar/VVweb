# userprofiles/signals.py

from django.dispatch import receiver
from allauth.account.signals import user_signed_up, email_confirmed
from django.utils import timezone

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
# COMMERCIAL CHECK → Central helper
# ======================================================================
def enforce_commercial_quota(user, profile):
    """
    Enforce commercial subscription rules:

      - Triggered if:
          org_type == commercial
          OR
          verification_status == commercial

      - Result:
          plan = commercial
          custom_limit = None
          subscription_expires = None
          count reset
    """

    # Combined rule
    is_commercial = (
        (profile.org_type == "commercial") or
        (profile.verification_status == "commercial")
    )

    if not is_commercial:
        return  # No action needed

    try:
        quota = VariantQuota.objects.get(user=user)
    except VariantQuota.DoesNotExist:
        quota = VariantQuota.objects.create(
            user=user,
            plan="commercial",
            count=0,
            custom_limit=None,
            subscription_expires=None,
            last_reset=timezone.now(),
        )
        logger.info(f"[commercial_enforce] Created new COMMERCIAL plan for {user.username}")
        return

    # Already correct → nothing to do
    if quota.plan == "commercial":
        return

    # Apply enforced commercial settings
    quota.plan = "commercial"
    quota.custom_limit = None
    quota.subscription_expires = None
    quota.count = 0
    quota.last_reset = timezone.now()
    quota.save()

    logger.info(
        f"[commercial_enforce] Updated VariantQuota for {user.username}: "
        f"plan=commercial"
    )


# ======================================================================
# EMAIL CONFIRMED → SYNC PROFILE + INSTITUTION MEMBERSHIP + COMMERCIAL ENFORCEMENT
# IMPORTANT: Signature must include `sender` as first param
# ======================================================================
@receiver(email_confirmed)
def handle_email_verified(sender, request, email_address, **kwargs):
    """
    When a user verifies an email:
      1. Mark email verified in UserProfile
      2. Update completion level
      3. Recompute institutional membership using ALL verified emails
      4. Update VariantQuota.institution pointer
      5. Enforce commercial subscription if profile indicates so
    """

    user = email_address.user
    logger.info(f"[email_confirmed] Fired for user={user.username} email={email_address.email}")

    # -------------------------------------------------------
    # 1. Update profile
    # -------------------------------------------------------
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.email_is_verified = True
    profile.completion_level = profile.get_completion_level()
    profile.save()
    logger.info(f"[email_confirmed] email_is_verified=True set for {user.username}")

    # -------------------------------------------------------
    # 2. Gather verified domains
    # -------------------------------------------------------
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
        logger.info(f"[email_confirmed] No verified domains → cleared institution")
        enforce_commercial_quota(user, profile)
        return

    # -------------------------------------------------------
    # 3. Match institutions (suffix rule)
    # -------------------------------------------------------
    matches = []
    for inst_domain in InstitutionDomain.objects.select_related("institution"):
        inst_suffix = inst_domain.domain
        for d in verified_domains:
            if d == inst_suffix or d.endswith("." + inst_suffix):
                matches.append((inst_domain.institution, inst_suffix))

    if not matches:
        InstitutionMembership.objects.filter(user=user, active=True).update(active=False)
        VariantQuota.objects.filter(user=user).update(institution=None)
        logger.info(f"[email_confirmed] No institution match for {user.username}")
        enforce_commercial_quota(user, profile)
        return

    # -------------------------------------------------------
    # 4. Select best match: longest suffix wins
    # -------------------------------------------------------
    matches.sort(key=lambda x: len(x[1]), reverse=True)
    best_institution, best_domain = matches[0]

    # -------------------------------------------------------
    # 5. Create/activate membership
    # -------------------------------------------------------
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

    logger.info(
        f"[email_confirmed] {user.username} → institution '{best_institution.name}' "
        f"(matched via '{best_domain}')"
    )

    # -------------------------------------------------------
    # 6. Deactivate other memberships
    # -------------------------------------------------------
    InstitutionMembership.objects.filter(
        user=user,
        active=True
    ).exclude(institution=best_institution).update(active=False)

    # -------------------------------------------------------
    # 7. Update quota institution pointer
    # -------------------------------------------------------
    try:
        quota = VariantQuota.objects.get(user=user)
    except VariantQuota.DoesNotExist:
        logger.warning(f"[email_confirmed] Missing VariantQuota for {user.username}")
        quota = VariantQuota.objects.create(user=user)

    if quota.institution != best_institution:
        quota.institution = best_institution
        quota.save()
        logger.info(
            f"[email_confirmed] quota institution → {best_institution.name}"
        )

    # -------------------------------------------------------
    # 8. ENFORCE commercial quota (combined rule)
    # -------------------------------------------------------
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