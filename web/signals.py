# web/signals.py
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from allauth.account.signals import user_signed_up
from allauth.account.models import EmailAddress
from .models import VariantQuota, Contact
import logging

logger = logging.getLogger('vv')


@receiver(post_save, sender=User)
def create_variant_quota(sender, instance, created, **kwargs):
    """Automatically create VariantQuota for new users"""
    if created:
        VariantQuota.objects.create(
            user=instance,
            plan='standard',
            count=0,
            last_reset=timezone.now()
        )
        logger.info(f"Created VariantQuota for new user: {instance.username}")


@receiver(user_signed_up)
def create_contact_for_new_user(request, user, **kwargs):
    """Create Contact object if user's email is verified"""
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
