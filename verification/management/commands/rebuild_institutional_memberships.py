# verification/management/commands/rebuild_institutional_memberships.py

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.test.client import RequestFactory

from allauth.account.models import EmailAddress
from allauth.account.signals import email_confirmed

from userprofiles.models import UserProfile
from web.models import VariantQuota


class Command(BaseCommand):
    help = (
        "Rebuild institutional membership + VariantQuota.institution for ALL verified users.\n"
        "Uses PRIMARY EMAIL ONLY. Unverified users are ignored.\n"
        "Does NOT auto-verify anyone. Does NOT override verification rules."
    )

    def handle(self, *args, **options):
        rf = RequestFactory()

        users = User.objects.all()
        total = users.count()

        fixed_email = 0
        inst_triggered = 0
        q_created = 0

        self.stdout.write(self.style.WARNING(f"Processing {total} users..."))

        for user in users:
            profile = getattr(user, "profile", None)
            if not profile:
                continue

            # ---------------------------------------------------------
            # Ensure VariantQuota exists
            # ---------------------------------------------------------
            try:
                quota = user.variant_quota
            except VariantQuota.DoesNotExist:
                quota = VariantQuota.objects.create(user=user)
                q_created += 1

            # ---------------------------------------------------------
            # Ensure PRIMARY EmailAddress exists
            # ---------------------------------------------------------
            try:
                ea = EmailAddress.objects.get(user=user, email=user.email, primary=True)
            except EmailAddress.DoesNotExist:
                ea = EmailAddress.objects.create(
                    user=user,
                    email=user.email,
                    primary=True,
                    verified=False,
                )
                fixed_email += 1

            # ---------------------------------------------------------
            # Sync verification flag from user profile
            # ---------------------------------------------------------
            if profile.email_is_verified and not ea.verified:
                ea.verified = True
                ea.save()
                fixed_email += 1

            if not profile.email_is_verified and ea.verified:
                ea.verified = False
                ea.save()
                fixed_email += 1

            # ---------------------------------------------------------
            # Only run institutional linking if:
            #   • primary email verified
            #   • AND user is validated (verified / auto_verified / commercial)
            # ---------------------------------------------------------
            validated = profile.verification_status in ("verified", "auto_verified", "commercial")

            if ea.verified and validated:
                request = rf.get("/")
                email_confirmed.send(sender=None, request=request, email_address=ea)
                inst_triggered += 1

        # ---------------------------------------------------------
        # Summary
        # ---------------------------------------------------------
        self.stdout.write(self.style.SUCCESS("Institution rebuild complete."))
        self.stdout.write(self.style.SUCCESS(f"Primary EmailAddress records updated: {fixed_email}"))
        self.stdout.write(self.style.SUCCESS(f"Institution logic triggered for: {inst_triggered} users"))
        self.stdout.write(self.style.SUCCESS(f"VariantQuota created: {q_created}"))

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
