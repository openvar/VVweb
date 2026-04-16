# tests/accounts/test_verified_redirect.py

import pytest
from django.urls import reverse
from django.contrib.auth import get_user_model
from allauth.account.models import EmailAddress

User = get_user_model()


@pytest.mark.django_db(transaction=True)
def test_unverified_user_redirected_to_confirm_page_on_login(client):
    # Create user
    user = User.objects.create_user(
        username="loginuser",
        email="login@example.com",
        password="StrongPassword123!",
    )

    # Explicitly create unverified EmailAddress (matches login enforcement)
    EmailAddress.objects.create(
        user=user,
        email=user.email,
        primary=True,
        verified=False,
    )

    response = client.post(
        "/accounts/login/",
        data={
            "login": "login@example.com",
            "password": "StrongPassword123!",
        },
        follow=False,
    )

    # StrictLoginView redirects unverified users here
    assert response.status_code == 302
    assert response.url == reverse("account_email_verification_sent")

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