# web/signals.py

import logging
from django.utils import timezone
from django.dispatch import receiver
from django.db.models.signals import post_save, post_migrate
from django.db.utils import OperationalError, ProgrammingError
from django.contrib.auth import get_user_model

from allauth.account.signals import user_signed_up
from allauth.account.models import EmailAddress

from web.models import VariantQuota, Contact
from userprofiles.models import UserProfile

logger = logging.getLogger(__name__)

User = get_user_model()


# ======================================================================
# PROFILE + QUOTA CREATION ON NEW USER
# ======================================================================
@receiver(post_save, sender=User)
def ensure_profile_and_quota_on_create(sender, instance, created, **kwargs):
    """
    Ensure every newly-created user has:
      - a UserProfile
      - a VariantQuota

    This is what tests and application logic rely on.
    """
    if not created:
        return

    UserProfile.objects.get_or_create(user=instance)

    VariantQuota.objects.get_or_create(
        user=instance,
        defaults={
            "plan": "standard",
            "count": 0,
            "last_reset": timezone.now(),
        },
    )

    logger.info(
        "[user_init] Created profile + quota for new user: %s",
        instance.username,
    )


# ======================================================================
# CREATE CONTACT WHEN USER SIGNS UP WITH VERIFIED EMAIL
# ======================================================================
@receiver(user_signed_up)
def create_contact_for_new_user(request, user, **kwargs):
    """
    Create a Contact object if the user's email is verified at signup.
    """
    email_obj = EmailAddress.objects.filter(user=user, verified=True).first()
    if not email_obj:
        return

    Contact.objects.get_or_create(
        emailval=email_obj.email,
        defaults={
            "name": user.get_full_name() or user.username,
            "variant": "",
            "question": "(auto-created on signup)",
        },
    )

    logger.info("[contact_created] Created Contact for new user: %s", user.username)


# ======================================================================
# BULK REPAIR FOR EXISTING USERS (AUTO, MIGRATION-SAFE)
# ======================================================================
@receiver(post_migrate)
def sync_all_users_after_migrate(sender, **kwargs):
    """
    Ensure *existing* users (from before quota logic existed)
    have a VariantQuota and sane defaults.

    Runs automatically:
      - after migrations
      - after test DB creation
      - after fresh deploys / restores

    Never runs at import time.
    """
    # Only run once per app migrate, not for every app
    if sender.name != "web":
        return

    try:
        if not User.objects.exists():
            return

        for user in User.objects.all():
            quota, _ = VariantQuota.objects.get_or_create(
                user=user,
                defaults={
                    "plan": "standard",
                    "count": 0,
                    "last_reset": timezone.now(),
                },
            )

            # Normalise legacy / bad data
            if quota.plan in (None, ""):
                quota.plan = "standard"
                quota.save(update_fields=["plan"])

        logger.info("[post_migrate] User quota sync complete.")

    except (OperationalError, ProgrammingError):
        # Tables not ready yet (e.g. during migrate)
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