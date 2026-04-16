import pytest
from django.core import mail


@pytest.mark.django_db(transaction=True)
def test_confirmation_email_contains_confirmation_link(client):
    client.post(
        "/accounts/signup/",
        data={
            "email": "confirm@example.com",
            "username": "confirmuser",
            "password1": "VeryStrongPassword123!",
            "password2": "VeryStrongPassword123!",
            "g-recaptcha-response": "PASSTEST",
        },
    )

    assert len(mail.outbox) == 1
    email = mail.outbox[0]

    assert "confirm" in email.body.lower()

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