import pytest
from django.contrib.auth.models import User


@pytest.mark.django_db
def test_auto_verified_user_bypasses_verification(
    client, verify_email, submit_verification_form
):
    user = User.objects.create_user(
        username="auto_user",
        email="user@university.ac.uk",
        password="StrongPass123!",
    )

    verify_email(user)
    client.login(username=user.username, password="StrongPass123!")
    submit_verification_form()

    # Auto-verified users should not remain in verification UI
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