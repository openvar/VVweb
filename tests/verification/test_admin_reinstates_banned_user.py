import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone


@pytest.mark.django_db
def test_admin_can_reinstate_banned_user(
    client, verify_email, submit_verification_form
):
    user = User.objects.create_user(
        username="banned_then_saved",
        email="test@randomdomain.com",
        password="StrongPass123!",
    )

    # User submits verification
    verify_email(user)
    client.login(username=user.username, password="StrongPass123!")
    submit_verification_form()

    # --- ADMIN BANS USER ---
    profile = user.profile
    profile.verification_status = "banned"
    profile.save()

    client.logout()
    client.post(
        reverse("account_login"),
        data={"login": user.email, "password": "StrongPass123!"},
        follow=False,
    )

    response = client.get("/banned/", follow=False)
    assert response.status_code == 302

    # --- ADMIN REINSTATES USER ---
    admin = User.objects.create_superuser(
        username="admin",
        email="admin@example.com",
        password="AdminPass123!",
    )

    profile.verification_status = "verified"
    profile.verified_by = admin
    profile.verified_at = timezone.now()
    profile.save()

    client.logout()
    client.post(
        reverse("account_login"),
        data={"login": user.email, "password": "StrongPass123!"},
        follow=False,
    )

    # ✅ Reinstated users land on /
    response = client.get("/", follow=False)
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