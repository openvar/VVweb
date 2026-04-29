import pytest
from django.urls import reverse
from django.utils import timezone
from dateutil.relativedelta import relativedelta
from django.contrib.auth import get_user_model
from VVweb.web.models import VariantQuota

User = get_user_model()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "org_type",
    ["commercial", "commercial_healthcare"],
)
def test_commercial_users_blocked_after_trial_period_expires(
    client, verify_email, submit_verification_form, org_type
):
    user = User.objects.create_user(
        username=f"expired_{org_type}",
        email=f"expired_{org_type}@example.com",
        password="StrongPass123!",
    )

    verify_email(user)
    client.login(username=user.username, password="StrongPass123!")

    submit_verification_form(org_type)

    quota = VariantQuota.objects.get(user=user)

    # Simulate an active trial in the past
    quota.trial_redeemed = True
    quota.custom_limit = 20
    quota.last_reset = timezone.now() - relativedelta(months=1, minutes=1)
    quota.save()

    # Login triggers TierEnforcementMiddleware → reset_if_needed()
    response = client.post(
        reverse("account_login"),
        data={"login": user.email, "password": "StrongPass123!"},
        follow=False,
    )

    quota.refresh_from_db()

    # Trial period expired → allowance cleared by system
    assert quota.custom_limit is None
    assert quota.effective_allowance == 0

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