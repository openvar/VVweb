# web/apps.py
from django.apps import AppConfig
import logging

logger = logging.getLogger('vv')


class WebConfig(AppConfig):
    name = 'web'

    def ready(self):
        """
        Auto-create VariantQuota for existing and new users.
        Also create Contact for users signing up via allauth.
        """
        from django.conf import settings
        from django.contrib.auth.models import User
        from django.utils import timezone
        from django.db import transaction
        from django.db.utils import OperationalError, ProgrammingError
        from django.db.models.signals import post_save
        from django.dispatch import receiver
        from .models import VariantQuota, Contact
        from allauth.account.signals import user_signed_up
        from allauth.account.models import EmailAddress

        # -----------------------------
        # SIGNAL: Create VariantQuota for new users
        # -----------------------------
        @receiver(post_save, sender=User)
        def create_variant_quota(sender, instance, created, **kwargs):
            if created:
                VariantQuota.objects.create(
                    user=instance,
                    plan='standard',
                    count=0,
                    last_reset=timezone.now()
                )
                logger.info(f"Created VariantQuota for new user: {instance.username}")

        # -----------------------------
        # SIGNAL: Create Contact for verified signup
        # -----------------------------
        @receiver(user_signed_up)
        def create_contact_for_new_user(request, user, **kwargs):
            # Only create Contact if email is verified
            email_obj = EmailAddress.objects.filter(user=user, verified=True).first()
            if email_obj:
                Contact.objects.get_or_create(
                    emailval=email_obj.email,
                    defaults={
                        'name': user.get_full_name() or user.username,
                        'message': '',
                        'subscribed': True
                    }
                )
                logger.info(f"Created Contact for new user: {user.username}")

        # -----------------------------
        # FUNCTION: Sync existing users
        # -----------------------------
        def sync_existing_users():
            default_limit = getattr(settings, "DEFAULT_MONTHLY_VARIANT_ALLOWANCE", 20)
            updated_count = 0

            for user in User.objects.all():
                quota, created = VariantQuota.objects.get_or_create(
                    user=user,
                    defaults={
                        'plan': 'standard',
                        'count': 0,
                        'last_reset': timezone.now()
                    }
                )
                if not created and (quota.plan is None or quota.plan == ''):
                    quota.plan = 'standard'
                    quota.save()
                    updated_count += 1

            if updated_count > 0:
                print(f"Updated {updated_count} existing users to standard plan")

        # -----------------------------
        # TRY TO RUN IMMEDIATELY
        # -----------------------------
        try:
            # Only attempt if table exists
            if VariantQuota.objects.exists() or User.objects.exists():
                sync_existing_users()
        except (OperationalError, ProgrammingError):
            # Table doesn't exist yet (during makemigrations/migrate)
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
