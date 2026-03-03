# verification/management/commands/lowercase_emails.py

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from allauth.account.models import EmailAddress

class Command(BaseCommand):
    help = (
        "Lowercase ALL user emails and EmailAddress entries. "
        "Run ONCE ONLY after deploying new lowercase enforcement."
    )

    def handle(self, *args, **options):
        updated_users = 0
        updated_emails = 0

        # Lowercase User.email
        for u in User.objects.all():
            lower = u.email.lower().strip()
            if u.email != lower:
                u.email = lower
                u.save(update_fields=["email"])
                updated_users += 1

        # Lowercase EmailAddress.email
        for ea in EmailAddress.objects.all():
            lower = ea.email.lower().strip()
            if ea.email != lower:
                ea.email = lower
                ea.save(update_fields=["email"])
                updated_emails += 1

        self.stdout.write(self.style.SUCCESS(
            f"Done. Lowercased {updated_users} User emails and {updated_emails} EmailAddress emails."
        ))

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
