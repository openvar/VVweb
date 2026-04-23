from django.utils import timezone
from django.utils.deprecation import MiddlewareMixin


class PrimaryEmailResetMiddleware(MiddlewareMixin):
    """
    Detects primary email changes and triggers an automatic
    UserProfile revalidation reset.

    This middleware:
    - compares User.email with UserProfile.verified_email
    - sets reset_reason='auto' if they differ
    - does NOT touch allauth email verification
    - does NOT redirect or send emails
    """

    def process_request(self, request):
        user = getattr(request, "user", None)

        # Only act for authenticated users with a profile
        if not user or not user.is_authenticated:
            return

        profile = getattr(user, "profile", None)
        if profile is None:
            return

        # Need both a current email and a previously captured snapshot
        if not user.email or not profile.verified_email:
            return

        current_email = user.email.strip().lower()
        snapshot_email = profile.verified_email.strip().lower()

        # No change → nothing to do
        if current_email == snapshot_email:
            return

        # Already reset → do not repeat
        if profile.reset_reason is not None:
            return

        # --------------------------------------------------
        # PRIMARY EMAIL HAS CHANGED → AUTO RESET
        # --------------------------------------------------
        profile.reset_reason = "auto"
        profile.reset_at = timezone.now()

        profile.save(update_fields=[
            "reset_reason",
            "reset_at",
        ])

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
