import pytest
from django.contrib.auth.models import User
from django.urls import reverse


@pytest.mark.django_db
def test_admin_bans_pending_user_after_verification(
    client, verify_email, submit_verification_form
):
    user = User.objects.create_user(
        username="bad_user",
        email="bad@randomdomain.com",
        password="StrongPass123!",
    )

    # User verifies email and submits verification
    verify_email(user)
    client.login(username=user.username, password="StrongPass123!")

    response = submit_verification_form()
    assert response.url == "/verify/pending/"

    # Pending users remain in verification
    response = client.get("/verify/pending/")
    assert response.status_code == 200

    # --- ADMIN ACTION ---
    profile = user.profile
    profile.verification_status = "banned"
    profile.save()

    # User comes back later (fresh session)
    client.logout()
    client.post(
        reverse("account_login"),
        data={"login": user.email, "password": "StrongPass123!"},
        follow=False,
    )

    # ✅ User is taken to banned landing
    response = client.get("/banned/", follow=False)
    assert response.status_code == 302

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