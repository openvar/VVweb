import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "org_type",
    ["commercial", "commercial_healthcare"],
)
def test_new_commercial_user_is_gated_to_commercial_page(
    client, verify_email, submit_verification_form, org_type
):
    user = User.objects.create_user(
        username=f"login_{org_type}",
        email=f"login_{org_type}@example.com",
        password="StrongPass123!",
    )

    verify_email(user)
    client.login(username=user.username, password="StrongPass123!")

    # Complete real verification
    submit_verification_form(org_type)

    # Accessing the app root should be blocked for commercial users
    response = client.get("/", follow=False)

    assert response.status_code == 302
    assert response.url == "/commercial/"

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