# web/apps.py
from django.apps import AppConfig
import logging

logger = logging.getLogger("VVweb")


class WebConfig(AppConfig):
    name = "web"

    def ready(self):
        """
        Load signals, ensure VariantQuota exists for all users,
        and auto-assign institutional membership + cached institution
        based on verified email domains.
        """
        from . import signals #  Do not remove. Required import
        from django.contrib.auth.models import User
        from django.utils import timezone
        from django.db.utils import OperationalError, ProgrammingError

        from web.models import (
            VariantQuota,
            InstitutionDomain,
            InstitutionMembership,
        )

        logger.info("Web app initialising VariantValidator quota + institution system...")

        # -------------------------------------------------------
        # Reconcile django-celery-beat task names (auto-heal)
        # -------------------------------------------------------
        try:
            from django_celery_beat.models import PeriodicTask

            TASK_RENAMES = {
                old: new
                for old, new in {
                    "web.tasks.delete_old_users": "system.delete_old_users",
                    "web.tasks.email_old_users": "system.email_old_users",
                    "web.tasks.delete_old_jobs": "system.delete_old_jobs",
                }.items()
                if old != new
            }

            for old, new in TASK_RENAMES.items():
                updated = PeriodicTask.objects.filter(task=old).update(task=new)
                if updated:
                    logger.info(
                        f"Updated {updated} periodic task(s): {old} → {new}"
                    )

        # Beat tables may not exist during migrate
        except (OperationalError, ProgrammingError) as e:
            logger.debug("Celery beat tables not ready yet (%s)", e)

        # -------------------------------------------------------
        # Helper: Extract domain from an email
        # -------------------------------------------------------
        def extract_domain(email: str) -> str:
            try:
                return email.split("@", 1)[1].lower().strip()
            except Exception:
                return ""

        # -------------------------------------------------------
        # Find best institution for a domain using longest-suffix match
        # -------------------------------------------------------
        def find_matching_institution(domain: str):
            """
            Matches InstitutionDomain entries using a suffix rule
            (correct for NHS, universities, multi-level subdomains).

            If multiple matches exist, choose the one with the longest
            domain suffix (most specific match).
            """
            if not domain:
                return None

            # Get all suffix matches
            matches = []
            for inst_domain in InstitutionDomain.objects.select_related("institution"):
                if domain == inst_domain.domain or domain.endswith("." + inst_domain.domain):
                    matches.append(inst_domain)

            if not matches:
                return None

            # Choose the longest domain (e.g. trust.nhs.uk beats nhs.uk)
            matches.sort(key=lambda d: len(d.domain), reverse=True)
            return matches[0].institution

        # -------------------------------------------------------
        # Sync all users at startup:
        #   - ensure VariantQuota exists
        #   - assign institution membership if domain matches
        #   - update cached VariantQuota.institution
        # -------------------------------------------------------
        def sync_all_users():
            created_quotas = 0
            updated_plans = 0
            membership_created = 0
            membership_activated = 0
            membership_deactivated = 0

            for user in User.objects.all():
                # --- Ensure VariantQuota exists ---
                quota, created = VariantQuota.objects.get_or_create(
                    user=user,
                    defaults={
                        "plan": "standard",
                        "count": 0,
                        "last_reset": timezone.now(),
                    },
                )
                if created:
                    created_quotas += 1

                # Empty or null plan → standard
                if quota.plan in (None, ""):
                    quota.plan = "standard"
                    quota.save()
                    updated_plans += 1

                # --- Institution sync based on domain ---
                user_domain = extract_domain(user.email)
                institution = find_matching_institution(user_domain)

                # Get existing membership if any
                membership = (
                    InstitutionMembership.objects.filter(user=user, institution__active=True)
                    .order_by("-verified_at")
                    .first()
                )

                if institution:
                    # User should belong to this institution
                    if not membership:
                        # Create new membership
                        InstitutionMembership.objects.create(
                            user=user,
                            institution=institution,
                            source="domain",
                            email_used=user.email,
                            verified_at=timezone.now(),  # startup best guess
                            active=True,
                        )
                        membership_created += 1
                        membership = (
                            InstitutionMembership.objects.filter(
                                user=user, institution=institution, active=True
                            ).first()
                        )
                    else:
                        # Activate if inactive
                        if not membership.active:
                            membership.active = True
                            membership.verified_at = timezone.now()
                            membership.save()
                            membership_activated += 1

                    # Update cached quota pointer
                    if quota.institution_id != membership.institution_id:
                        quota.institution = membership.institution
                        quota.save()

                else:
                    # No matching institution → deactivate membership if exists
                    if membership and membership.active:
                        membership.active = False
                        membership.save()
                        membership_deactivated += 1

                    # Unset quota pointer
                    if quota.institution is not None:
                        quota.institution = None
                        quota.save()

            # Logging summary
            logger.info(
                f"Startup institution sync: "
                f"{created_quotas} quotas created, "
                f"{updated_plans} plans normalised, "
                f"{membership_created} memberships created, "
                f"{membership_activated} memberships activated, "
                f"{membership_deactivated} memberships deactivated."
            )

        logger.info("Web initialisation complete.")

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
