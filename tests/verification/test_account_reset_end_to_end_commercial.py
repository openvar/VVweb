import pytest
from datetime import timedelta

from django.contrib.auth.models import User
from django.utils import timezone
from allauth.account.models import EmailAddress


def advance_time(monkeypatch, days):
    frozen = timezone.now() + timedelta(days=days)
    monkeypatch.setattr("django.utils.timezone.now", lambda: frozen)


@pytest.mark.django_db
def test_commercial_user_cannot_auto_downgrade_to_noncommercial(
    client, verify_email, submit_verification_form, monkeypatch
):
    """
    Policy under test (authoritative):

    • Commercial users cannot auto‑approve into non‑commercial
    • This holds EVEN WITH trusted email domains
    • After auto‑reset, email + terms must be re‑verified
    • After re‑verification, downgrade MUST be pending admin review
    """

    # ------------------------------------------------------------
    # 1. Create user (untrusted domain is fine here)
    # ------------------------------------------------------------
    user = User.objects.create_user(
        username="commercial_user",
        email="user@somedomain.com",
        password="StrongPass123!",
    )

    # Initial email verification (creates ONE EmailAddress row)
    verify_email(user)

    client.login(username=user.username, password="StrongPass123!")

    # ------------------------------------------------------------
    # 2. Initial verification as COMMERCIAL
    # ------------------------------------------------------------
    submit_verification_form(org_type="commercial")

    user.profile.refresh_from_db()
    assert user.profile.verification_status == "commercial"
    assert user.profile.reset_reason is None

    # ------------------------------------------------------------
    # 3. Auto‑reset after 1 year (compliance reset only)
    # ------------------------------------------------------------
    advance_time(monkeypatch, days=366)

    client.logout()
    client.login(username=user.username, password="StrongPass123!")

    # Trigger TierEnforcementMiddleware
    response = client.get("/", follow=False)

    user.profile.refresh_from_db()
    assert user.profile.reset_reason == "auto"

    # ✅ IMPORTANT FIX:
    # Auto‑reset DOES NOT wipe identity provenance
    assert user.profile.verification_status == "commercial"

    assert user.profile.terms_accepted_at is None

    # Email MUST be re‑verified first
    assert response.status_code == 302
    assert response.url == "/accounts/confirm-email/"

    # ------------------------------------------------------------
    # 4. Simulate EMAIL RE‑VERIFICATION (no new rows)
    # ------------------------------------------------------------
    EmailAddress.objects.filter(user=user).update(verified=True)

    # ------------------------------------------------------------
    # 5. User attempts downgrade to NON‑COMMERCIAL
    # ------------------------------------------------------------
    response = submit_verification_form(
        org_type="university",
        finalize=False,  # 🔑 CRITICAL LINE
    )

    # ------------------------------------------------------------
    # 6. MUST require admin review
    # ------------------------------------------------------------
    assert response.status_code == 302
    assert response.url == "/verify/pending/"

    user.profile.refresh_from_db()
    assert user.profile.verification_status == "pending"
    assert user.profile.reset_reason == "auto"
    assert user.profile.org_type == "university"

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
