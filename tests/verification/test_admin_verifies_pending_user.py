import pytest
from django.contrib.auth.models import User
from django.utils import timezone


@pytest.mark.django_db
def test_pending_user_admin_verified_gets_standard_access(
    client, verify_email, submit_verification_form
):
    user = User.objects.create_user(
        username="pending_user",
        email="someone@randomdomain.com",
        password="StrongPass123!",
    )

    verify_email(user)
    client.login(username=user.username, password="StrongPass123!")
    submit_verification_form()

    # Pending user remains in verification flow
    response = client.get("/verify/pending/")
    assert response.status_code == 200

    admin = User.objects.create_superuser(
        username="admin",
        email="admin@example.com",
        password="AdminPass123!",
    )

    profile = user.profile
    profile.verification_status = "verified"
    profile.verified_at = timezone.now()
    profile.verified_by = admin
    profile.save()

    # Verified users exit verification UI
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