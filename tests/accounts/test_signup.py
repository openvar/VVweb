import pytest
from django.core import mail
from django.contrib.auth import get_user_model
from allauth.account.models import EmailAddress

User = get_user_model()


@pytest.mark.django_db(transaction=True)
def test_signup_creates_user_and_sends_confirmation_email(client):
    response = client.post(
        "/accounts/signup/",
        data={
            "email": "test@example.com",
            "username": "testuser",
            "password1": "VeryStrongPassword123!",
            "password2": "VeryStrongPassword123!",
            "g-recaptcha-response": "PASSTEST",
        },
        follow=False,
    )

    # ✅ Correct behavior: redirect to confirm-email page
    assert response.status_code == 302
    assert response.url == "/accounts/confirm-email/"

    # ✅ User created
    user = User.objects.get(email="test@example.com")

    # ✅ EmailAddress exists and is unverified
    email_obj = EmailAddress.objects.get(user=user, email=user.email)
    assert email_obj.primary is True
    assert email_obj.verified is False

    # ✅ Confirmation email sent
    assert len(mail.outbox) == 1

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