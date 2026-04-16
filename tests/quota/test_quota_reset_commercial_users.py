import pytest
from datetime import timedelta
from django.utils import timezone


@pytest.fixture
def commercial_user_with_pro_plan(django_user_model):
    user = django_user_model.objects.create_user(
        username="commercial_pro_user",
        email="commercial_pro@example.com",
        password="StrongPass123!",
    )

    profile = user.profile
    profile.verification_status = "commercial"
    profile.save(update_fields=["verification_status"])

    quota = user.variant_quota
    quota.plan = "pro"  # ✅ paid tier, identity from profile
    quota.subscription_expires = timezone.now() + timedelta(days=30)
    quota.count = 0
    quota.custom_limit = None
    quota.save()

    return user


@pytest.fixture
def commercial_user_with_enterprise_plan(django_user_model):
    user = django_user_model.objects.create_user(
        username="commercial_enterprise_user",
        email="commercial_enterprise@example.com",
        password="StrongPass123!",
    )

    profile = user.profile
    profile.verification_status = "commercial"
    profile.save(update_fields=["verification_status"])

    quota = user.variant_quota
    quota.plan = "enterprise"
    quota.subscription_expires = timezone.now() + timedelta(days=30)
    quota.count = 0
    quota.custom_limit = None
    quota.save()

    return user

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
