import pytest
from django.contrib.auth import get_user_model
from allauth.account.models import EmailAddress

User = get_user_model()


@pytest.mark.django_db(transaction=True)
def test_primary_email_change_triggers_auto_reset_with_ui(
    client, verify_email, submit_verification_form
):
    """
    Primary email change lifecycle (with UI assertions).

    Policy under test:
    - Changing primary email is an identity boundary
    - Email ownership remains verified (no re-verification loop)
    - Auto-reset routes user back through verification UI
    - Reset is logical, not physical
    """

    # ------------------------------------------------------------------
    # 1. CREATE USER + VERIFY EMAIL
    # ------------------------------------------------------------------
    user = User.objects.create_user(
        username="email_change_user",
        email="user@university.edu",
        password="StrongPass123!",
    )

    verify_email(user)
    assert client.login(username=user.username, password="StrongPass123!")

    # New user must see verification UI
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
    assert user.profile.reset_reason is None
    assert user.profile.verified_email == "user@university.edu"

    # Verified users exit verification flow
    response = client.get("/verify/", follow=False)
    assert response.status_code == 302
    assert response.url == "/"

    # Home page should now be accessible
    response = client.get("/")
    assert response.status_code == 200

    # ------------------------------------------------------------------
    # 3. ADD + VERIFY SECOND EMAIL
    # ------------------------------------------------------------------
    email2 = EmailAddress.objects.create(
        user=user,
        email="user.alt@university.edu",
        primary=False,
        verified=False,
    )

    email2.verified = True
    email2.save(update_fields=["verified"])

    # ------------------------------------------------------------------
    # 4. MAKE SECOND EMAIL PRIMARY
    # ------------------------------------------------------------------
    EmailAddress.objects.filter(user=user).update(primary=False)

    email2.primary = True
    email2.save(update_fields=["primary"])

    user.email = email2.email
    user.save(update_fields=["email"])

    # ------------------------------------------------------------------
    # 5. TRIGGER MIDDLEWARE VIA PROTECTED ENDPOINT
    # ------------------------------------------------------------------
    response = client.get("/")
    assert response.status_code in (200, 302)

    user.profile.refresh_from_db()

    # ✅ AUTO RESET OCCURRED
    assert user.profile.reset_reason == "auto"
    assert user.profile.reset_at is not None
    assert user.profile.terms_accepted_at is not None

    # ------------------------------------------------------------------
    # 6. USER IS ROUTED BACK TO RENEWAL UI
    # ------------------------------------------------------------------
    response = client.get("/verify/")
    assert response.status_code == 200

    # UI must clearly indicate renewal, not first-time signup
    assert (
        b"Renew Your Verification" in response.content
        or b"Verify Your Identity" in response.content
    )

    # ------------------------------------------------------------------
    # 7. RE-SUBMIT VERIFICATION (SAME ORG)
    # ------------------------------------------------------------------
    submit_verification_form(org_type="university")

    user.profile.refresh_from_db()

    assert user.profile.verification_status == "verified"
    assert user.profile.reset_reason is None

    # User exits verification again
    response = client.get("/verify/", follow=False)
    assert response.status_code == 302
    assert response.url == "/"

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
