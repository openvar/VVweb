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
    VariantQuota is created in web/signals.py.
    """
    profile, created = UserProfile.objects.get_or_create(user=user)
    if created:
        logger.info(f"[user_signed_up] Created UserProfile for {user.username}")
    else:
        logger.info(f"[user_signed_up] UserProfile already existed for {user.username}")


# ======================================================================
# EMAIL CONFIRMED → SYNC PROFILE + INSTITUTION MEMBERSHIP
# IMPORTANT: Signature must include `sender` as first param
# ======================================================================
@receiver(email_confirmed)
def handle_email_verified(sender, request, email_address, **kwargs):
    """
    When a user verifies an email:
      1. Mark the UserProfile as verified (email_is_verified=True) to avoid loops.
      2. Update profile completion level.
      3. Recompute institutional membership using ALL verified email domains
         (longest suffix match wins).
      4. Update user.variant_quota.institution pointer.
      5. Deactivate old memberships if no longer valid.
    """
    user = email_address.user
    logger.info(f"[email_confirmed] Fired for user={user.username} email={email_address.email}")

    # -------------------------------------------------------
    # 1. Update profile (avoid email-verification loop)
    # -------------------------------------------------------
    profile, _ = UserProfile.objects.get_or_create(user=user)
    profile.email_is_verified = True
    profile.completion_level = profile.get_completion_level()
    profile.save()
    logger.info(f"[email_confirmed] email_is_verified=True set for {user.username}")

    # -------------------------------------------------------
    # 2. Collect ALL verified email domains for this user
    # -------------------------------------------------------
    verified_emails = EmailAddress.objects.filter(user=user, verified=True)
    verified_domains = []

    for e in verified_emails:
        try:
            domain = e.email.split("@", 1)[1].lower().strip()
            if domain:
                verified_domains.append(domain)
        except Exception:
            continue

    if not verified_domains:
        # If the account has no verified domains, remove institution mappings.
        InstitutionMembership.objects.filter(user=user, active=True).update(active=False)
        VariantQuota.objects.filter(user=user).update(institution=None)
        logger.info(f"[email_confirmed] No verified email domains for {user.username}. Cleared institution pointers.")
        return

    # -------------------------------------------------------
    # 3. Find all matching institutions (suffix rule, multiple domains)
    # -------------------------------------------------------
    matches = []  # (Institution, matching_domain)

    for inst_domain in InstitutionDomain.objects.select_related("institution"):
        inst_suffix = inst_domain.domain
        for user_domain in verified_domains:
            if user_domain == inst_suffix or user_domain.endswith("." + inst_suffix):
                matches.append((inst_domain.institution, inst_suffix))

    if not matches:
        # Deactivate any existing memberships if no matches remain
        InstitutionMembership.objects.filter(user=user, active=True).update(active=False)
        VariantQuota.objects.filter(user=user).update(institution=None)
        logger.info(f"[email_confirmed] No institution matched for {user.username}. Cleared institution pointers.")
        return

    # -------------------------------------------------------
    # 4. Choose the BEST match: longest domain suffix wins
    # -------------------------------------------------------
    matches.sort(key=lambda pair: len(pair[1]), reverse=True)
    best_institution, best_domain = matches[0]

    # -------------------------------------------------------
    # 5. Get or create membership
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
        # Ensure active and capture the email_used + timestamp
        if not membership.active:
            membership.active = True
        membership.email_used = email_address.email
        membership.verified_at = timezone.now()
        membership.save()

    logger.info(
        f"[email_confirmed] {user.username} → institution '{best_institution.name}' "
        f"(matched via '{best_domain}')"
    )

    # -------------------------------------------------------
    # 6. Deactivate any other memberships
    # -------------------------------------------------------
    InstitutionMembership.objects.filter(
        user=user,
        active=True
    ).exclude(institution=best_institution).update(active=False)

    # -------------------------------------------------------
    # 7. Update VariantQuota.institution pointer (cached on quota)
    # -------------------------------------------------------
    try:
        quota = VariantQuota.objects.get(user=user)
    except VariantQuota.DoesNotExist:
        logger.warning(f"[email_confirmed] VariantQuota missing for user {user.username}")
        return

    if quota.institution != best_institution:
        quota.institution = best_institution
        quota.save()
        logger.info(
            f"[email_confirmed] VariantQuota updated for {user.username}: "
            f"institution = {best_institution.name}"
        )
    else:
        logger.info(
            f"[email_confirmed] VariantQuota unchanged for {user.username}: "
            f"institution = {best_institution.name}"
        )

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