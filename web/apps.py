# web/apps.py
from django.apps import AppConfig
import logging

logger = logging.getLogger('vv')

class WebConfig(AppConfig):
    name = 'web'

    def ready(self):
        # Import inside ready to avoid import-time ORM access
        from django.conf import settings
        from django.contrib.auth.models import User
        from .models import VariantQuota
        from django.db import transaction
        from django.db.utils import OperationalError, ProgrammingError

        # Schedule a post-commit function so ORM is fully ready
        def sync_free_tier_quotas():
            default_limit = getattr(settings, "DEFAULT_MONTHLY_VARIANT_ALLOWANCE", 20)
            updated_count = 0
            for user in User.objects.all():
                quota, created = VariantQuota.objects.get_or_create(user=user)
                # Only update if plan is None or missing
                if quota.plan is None:
                    quota.plan = "standard"
                    quota.save()
                    updated_count += 1

            if updated_count > 0:
                print(f"Updated {updated_count} Free-tier users to standard plan")

        # Only try to run if the table exists
        try:
            if VariantQuota.objects.exists():
                transaction.on_commit(sync_free_tier_quotas)
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
