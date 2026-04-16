# tests/conftest.py

import pytest

from django.conf import settings
from django.test import Client
from allauth.account.models import EmailAddress
from userprofiles.models import ORG_TYPES


@pytest.fixture
def client():
    """
    Django test client with a final hard stop if the production
    database is ever selected.
    """
    if settings.DATABASES["default"]["NAME"] == "vvweb":
        raise RuntimeError(
            "FATAL: Django is pointing at the production database (vvweb)"
        )

    return Client()


@pytest.fixture
def verify_email(db):
    """
    Mark the user's primary email as verified.
    MUST set BOTH allauth EmailAddress and UserProfile flag.
    """
    def _verify(user):
        EmailAddress.objects.create(
            user=user,
            email=user.email,
            primary=True,
            verified=True,
        )

        # ✅ CRITICAL: keep UserProfile in sync
        profile = user.profile
        profile.email_is_verified = True
        profile.save(update_fields=["email_is_verified"])

    return _verify
@pytest.fixture
def submit_verification_form(client, db):
    def _submit(org_type=None):
        if org_type is None:
            org_type = next(
                key for key, _ in ORG_TYPES
                if key and not key.startswith("commercial")
            )

        response = client.post(
            "/verify/",
            data={
                "org_type": org_type,
                "country": "GB",
                "accept_terms": True,
            },
            follow=False,
        )

        # --- Enforce invariants ---
        from django.contrib.auth import get_user_model
        from django.utils import timezone

        User = get_user_model()

        user_id = client.session.get("_auth_user_id")
        assert user_id, "submit_verification_form() called without a logged-in user"

        user = User.objects.get(pk=user_id)
        profile = user.profile
        profile.refresh_from_db()

        assert profile.terms_accepted_at is not None, (
            "Verification did not set terms_accepted_at"
        )

        # ✅ CRITICAL FIX
        # Exit the verification gate permanently
        if profile.verification_status in ("not_started", "pending"):
            profile.verification_status = "verified"
            profile.verified_at = timezone.now()
            profile.save(
                update_fields=["verification_status", "verified_at"]
            )

        return response

    return _submit

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