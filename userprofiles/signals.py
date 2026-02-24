# userprofiles/signals.py

from django.dispatch import receiver
from allauth.account.signals import user_signed_up, email_confirmed
from django.conf import settings
from django.utils import timezone

from .models import UserProfile
from web.models import (
    Institution,
    InstitutionDomain,
    InstitutionMembership,
    VariantQuota,
)

import logging
logger = logging.getLogger('vv')


# -------------------------------------------------------
# NEW USER PROFILE CREATION (UNCHANGED)
# -------------------------------------------------------
@receiver(user_signed_up)
def create_user_profile(request, user, **kwargs):
    """
    Create a UserProfile when a new user signs up.
    VariantQuota is created in web/signals.py, so we don't duplicate it here.
    """
    profile, created = UserProfile.objects.get_or_create(user=user)
    if created:
        logger.info(f"Created UserProfile for {user.username}")


# ======================================================================
# EMAIL CONFIRMED → INSTITUTION MEMBERSHIP SYNC
# ======================================================================

@receiver(email_confirmed)
def handle_email_verified(request, email_address, **kwargs):
    """
    When a user verifies an email:
      1. Mark the UserProfile as verified (old behaviour preserved)
      2. Recompute institutional membership using ALL verified email domains
      3. Activate membership for best-matching institution (longest suffix match)
      4. Update user.variant_quota.institution pointer
      5. Deactivate old memberships if no longer valid
    """
    user = email_address.user

    # -------------------------------------------------------
    # 1. Update profile (existing behaviour)
    # -------------------------------------------------------
    profile = UserProfile.objects.get(user=user)
    profile.email_is_verified = True
    profile.completion_level = profile.get_completion_level()
    profile.save()
    logger.info(f"Email set as verified for {user.username}")

    # -------------------------------------------------------
    # 2. Collect ALL verified email domains for this user
    # -------------------------------------------------------
    from allauth.account.models import EmailAddress

    verified_emails = EmailAddress.objects.filter(user=user, verified=True)
    verified_domains = []

    for e in verified_emails:
        try:
            domain = e.email.split("@", 1)[1].lower().strip()
            verified_domains.append(domain)
        except Exception:
            pass

    if not verified_domains:
        logger.info(f"No verified email domains for user {user.username}.")
        return

    # -------------------------------------------------------
    # 3. Find all matching institutions (suffix rule, multiple domains)
    # -------------------------------------------------------
    matches = []  # (Institution, matching_domain)

    for inst_domain in InstitutionDomain.objects.select_related("institution"):
        for user_domain in verified_domains:
            if (
                user_domain == inst_domain.domain
                or user_domain.endswith("." + inst_domain.domain)
            ):
                matches.append((inst_domain.institution, inst_domain.domain))

    if not matches:
        # Deactivate any existing memberships
        InstitutionMembership.objects.filter(user=user, active=True).update(active=False)
        VariantQuota.objects.filter(user=user).update(institution=None)
        logger.info(f"User {user.username} has verified email(s) but no matching institution.")
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
        # Update existing membership if needed
        if not membership.active:
            membership.active = True
        membership.email_used = email_address.email
        membership.verified_at = timezone.now()
        membership.save()

    logger.info(
        f"User {user.username} assigned to institution '{best_institution.name}' "
        f"via domain '{best_domain}'."
    )

    # -------------------------------------------------------
    # 6. Deactivate any other memberships
    # -------------------------------------------------------
    InstitutionMembership.objects.filter(
        user=user,
        active=True
    ).exclude(institution=best_institution).update(active=False)

    # -------------------------------------------------------
    # 7. Update VariantQuota.institution pointer (cached)
    # -------------------------------------------------------
    quota = VariantQuota.objects.get(user=user)
    if quota.institution != best_institution:
        quota.institution = best_institution
        quota.save()

    logger.info(f"VariantQuota updated for user {user.username}: institution = {best_institution.name}")

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