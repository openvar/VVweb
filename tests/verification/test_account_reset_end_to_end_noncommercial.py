import pytest
from datetime import timedelta

from django.contrib.auth.models import User
from django.utils import timezone


def advance_time(monkeypatch, days):
    """
    Advance Django timezone.now() by the given number of days.
    Used to trigger annual auto-reset logic.
    """
    frozen = timezone.now() + timedelta(days=days)
    monkeypatch.setattr("django.utils.timezone.now", lambda: frozen)


@pytest.mark.django_db
def test_account_reset_noncommercial_full_lifecycle_known_user(
    client, verify_email, submit_verification_form, monkeypatch
):
    """
    Non-commercial KNOWN user lifecycle (email unchanged).

    Policy under test:
    - Email identity is preserved across resets (no duplicate EmailAddress rows)
    - Annual auto-reset forces re-confirmation of terms and org type
    - Known users are NOT sent back to pending
    - Switching to commercial is the only hard breakpoint
    - Auto-reset is triggered by any protected endpoint (here: `/`)
    """

    # ------------------------------------------------------------------
    # 1. CREATE USER (UNTRUSTED DOMAIN, BUT WILL BECOME "KNOWN")
    # ------------------------------------------------------------------
    user = User.objects.create_user(
        username="nc_known",
        email="user@randomdomain.com",  # deliberately not trusted
        password="StrongPass123!",
    )

    # Initial email verification (creates EmailAddress once)
    verify_email(user)
    client.login(username=user.username, password="StrongPass123!")

    # New user must see initial verification UI
    response = client.get("/verify/")
    assert response.status_code == 200
    assert b"Verify Your Identity" in response.content

    # ------------------------------------------------------------------
    # 2. INITIAL VERIFICATION (KNOWN USER ESTABLISHED)
    # ------------------------------------------------------------------
    submit_verification_form(org_type="university")

    user.profile.refresh_from_db()

    assert user.profile.verification_status == "verified"
    assert user.profile.is_verified() is True
    assert user.profile.verified_at is not None
    assert user.profile.reset_reason is None
    assert user.profile.terms_accepted_at is not None

    # Verified users exit verification flow
    response = client.get("/verify/", follow=False)
    assert response.status_code == 302
    assert response.url == "/"

    # ------------------------------------------------------------------
    # 3. FIRST ANNUAL AUTO-RESET (EMAIL + ORG UNCHANGED)
    #    Reset triggered by visiting `/`
    # ------------------------------------------------------------------
    advance_time(monkeypatch, days=366)

    client.logout()
    client.login(username=user.username, password="StrongPass123!")

    # Trigger middleware via protected endpoint
    response = client.get("/")
    assert response.status_code in (200, 302)

    user.profile.refresh_from_db()
    assert user.profile.reset_reason == "auto"
    assert user.profile.terms_accepted_at is None

    # Canonical renewal UI lives at /verify/
    response = client.get("/verify/")
    assert response.status_code == 200
    assert b"Renew Your Verification" in response.content

    # IMPORTANT:
    # We do NOT call verify_email(user) again.
    # EmailAddress already exists; reset is logical, not physical.

    # Re-submit with SAME non-commercial org type
    submit_verification_form(org_type="university")

    user.profile.refresh_from_db()
    assert user.profile.verification_status == "verified"
    assert user.profile.is_verified() is True
    assert user.profile.reset_reason is None

    # ------------------------------------------------------------------
    # 4. SECOND ANNUAL AUTO-RESET → SWITCH TO COMMERCIAL
    #    Again triggered via `/`
    # ------------------------------------------------------------------
    advance_time(monkeypatch, days=366)

    client.logout()
    client.login(username=user.username, password="StrongPass123!")

    response = client.get("/")
    assert response.status_code in (200, 302)

    user.profile.refresh_from_db()
    assert user.profile.reset_reason == "auto"

    response = client.get("/verify/")
    assert response.status_code == 200
    assert b"Renew Your Verification" in response.content

    # Again, no verify_email() call here.

    # Switching org type to commercial is the hard boundary
    response = submit_verification_form(org_type="commercial")

    assert response.status_code == 302
    assert response.url == "/commercial/"

    user.profile.refresh_from_db()
    assert user.profile.verification_status == "commercial"
    assert user.profile.org_type == "commercial"

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
