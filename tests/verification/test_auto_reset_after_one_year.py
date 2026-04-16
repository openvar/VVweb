import pytest
from datetime import timedelta
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
def test_auto_reset_after_one_year_forces_reverification(
    client, verify_email, submit_verification_form
):
    user = User.objects.create_user(
        username="expired_user",
        email="expired@randomdomain.com",
        password="StrongPass123!",
    )

    verify_email(user)
    client.login(username=user.username, password="StrongPass123!")

    submit_verification_form()

    profile = user.profile
    profile.verification_status = "verified"
    profile.terms_accepted_at = timezone.now() - timedelta(days=366)
    profile.save()

    response = client.get("/", follow=False)

    profile.refresh_from_db()

    assert profile.verification_status == "not_started"
    assert profile.reset_reason == "auto"
    assert profile.terms_accepted_at is None

    # Email reset is expected → confirm-email is REQUIRED first
    assert response.status_code == 302
    assert response.url == "/accounts/confirm-email/"

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