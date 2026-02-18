# web/apps.py
from django.apps import AppConfig
import logging

logger = logging.getLogger('vv')


class WebConfig(AppConfig):
    name = 'web'

    def ready(self):
        """
        Connect web app signals and sync existing users.
        """
        from . import signals
        from django.conf import settings
        from django.contrib.auth.models import User
        from .models import VariantQuota
        from django.utils import timezone
        from django.db.utils import OperationalError, ProgrammingError

        logger.info("Web signals loaded")

        # -----------------------------
        # Sync existing users at startup
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
                logger.info(f"Updated {updated_count} existing users to standard plan")

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
