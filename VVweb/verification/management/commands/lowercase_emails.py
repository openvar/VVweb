# verification/management/commands/lowercase_emails.py

from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db import transaction
from allauth.account.models import EmailAddress
from collections import defaultdict


class Command(BaseCommand):
    help = (
        "Resolve case-insensitive email duplicates safely, then lowercase all emails in "
        "User.email and EmailAddress.email. Run once.\n\n"
        "Strategy:\n"
        "  • Group users by lower(email)\n"
        "  • Keep one canonical user per group (primary+verified > earliest date_joined > lowest id)\n"
        "  • For non-canonicals: ensure EmailAddress exists (primary=False), then set User.email to a "
        "    unique placeholder: username.{id}@invalid.local\n"
        "  • Finally lowercase all User.email and EmailAddress.email"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would change without writing to the database.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        self.stdout.write(self.style.WARNING("Scanning for case-insensitive email collisions..."))

        # Build groups keyed by lowercased email
        groups = defaultdict(list)
        users = User.objects.all().only("id", "username", "email", "date_joined").order_by("id")

        for u in users:
            email = (u.email or "").strip()
            key = email.lower()
            if key:
                groups[key].append(u)

        collisions = {k: v for k, v in groups.items() if len(v) > 1}
        self.stdout.write(self.style.WARNING(f"Found {len(collisions)} collision group(s)."))

        fixed_users = 0
        kept_users = 0
        emailaddress_created = 0
        primaries_adjusted = 0

        def pick_canonical(user_list):
            """Prefer user with primary+verified EmailAddress, else earliest date_joined, else lowest id."""
            def rank(u):
                ea = EmailAddress.objects.filter(user=u, email__iexact=u.email).first()
                score_primary_verified = 1 if (ea and ea.primary and ea.verified) else 0
                return (-score_primary_verified, u.date_joined or u.id, u.id)
            return sorted(user_list, key=rank)[0]

        @transaction.atomic
        def resolve_group(key, user_list):
            nonlocal fixed_users, kept_users, emailaddress_created, primaries_adjusted

            canonical = pick_canonical(user_list)
            kept_users += 1

            # Ensure canonical has a primary EmailAddress row for their current email
            ea = EmailAddress.objects.filter(user=canonical, email__iexact=canonical.email).first()
            if not ea:
                if not dry_run:
                    EmailAddress.objects.create(
                        user=canonical,
                        email=(canonical.email or "").lower().strip(),
                        primary=True,
                        verified=False,  # don't assume; allauth will drive this later
                    )
                emailaddress_created += 1
            else:
                if not ea.primary and not dry_run:
                    ea.primary = True
                    ea.save(update_fields=["primary"])
                    primaries_adjusted += 1

            # Handle non-canonical users
            for u in user_list:
                if u.id == canonical.id:
                    continue

                # Ensure their EmailAddress row exists (non-primary)
                ea_nc = EmailAddress.objects.filter(user=u, email__iexact=u.email).first()
                if not ea_nc:
                    if not dry_run:
                        EmailAddress.objects.create(
                            user=u,
                            email=(u.email or "").lower().strip(),
                            primary=False,
                            verified=False,
                        )
                    emailaddress_created += 1
                else:
                    if ea_nc.primary and not dry_run:
                        ea_nc.primary = False
                        ea_nc.save(update_fields=["primary"])
                        primaries_adjusted += 1

                # Assign a unique placeholder email to avoid unique constraint collision
                placeholder = f"{u.username}.{u.id}@invalid.local".lower()
                if not dry_run:
                    u.email = placeholder
                    u.save(update_fields=["email"])
                fixed_users += 1

        # Resolve all collision groups
        for key, user_list in collisions.items():
            resolve_group(key, user_list)

        # SECOND PASS: Lowercase all User.email and EmailAddress.email (now safe — no collisions)
        updated_users = 0
        updated_emails = 0

        self.stdout.write(self.style.WARNING("Lowercasing User.email and EmailAddress.email..."))

        for u in User.objects.all().only("id", "email"):
            lower = (u.email or "").lower().strip()
            if u.email != lower:
                if not dry_run:
                    u.email = lower
                    u.save(update_fields=["email"])
                updated_users += 1

        for ea in EmailAddress.objects.all().only("id", "email"):
            lower = (ea.email or "").lower().strip()
            if ea.email != lower:
                if not dry_run:
                    ea.email = lower
                    ea.save(update_fields=["email"])
                updated_emails += 1

        # Summary
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no changes written."))

        self.stdout.write(self.style.SUCCESS("Completed. Summary:"))
        self.stdout.write(self.style.SUCCESS(f"  Collision groups:         {len(collisions)}"))
        self.stdout.write(self.style.SUCCESS(f"  Canonical kept:           {kept_users}"))
        self.stdout.write(self.style.SUCCESS(f"  Users set to placeholder: {fixed_users}"))
        self.stdout.write(self.style.SUCCESS(f"  EmailAddress created:     {emailaddress_created}"))
        self.stdout.write(self.style.SUCCESS(f"  Primaries adjusted:       {primaries_adjusted}"))
        self.stdout.write(self.style.SUCCESS(f"  Lowercased User rows:     {updated_users}"))
        self.stdout.write(self.style.SUCCESS(f"  Lowercased EmailAddress:  {updated_emails}"))

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
