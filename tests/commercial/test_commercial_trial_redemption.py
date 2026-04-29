import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from VVweb.web.models import VariantQuota

User = get_user_model()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "org_type",
    ["commercial", "commercial_healthcare"],
)
def test_commercial_trial_can_be_redeemed_once(
    client, verify_email, submit_verification_form, org_type
):
    user = User.objects.create_user(
        username=f"trial_{org_type}",
        email=f"trial_{org_type}@example.com",
        password="StrongPass123!",
    )

    verify_email(user)
    client.login(username=user.username, password="StrongPass123!")

    submit_verification_form(org_type)

    response = client.post("/commercial/redeem-trial/", follow=False)

    assert response.status_code == 302
    assert response.url == "/"

    quota = VariantQuota.objects.get(user=user)
    assert quota.trial_redeemed is True
    assert quota.custom_limit == settings.DEFAULT_MONTHLY_VARIANT_ALLOWANCE

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