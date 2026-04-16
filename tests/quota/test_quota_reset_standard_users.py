from datetime import timedelta
from django.utils import timezone
import pytest


@pytest.fixture
def user_with_pro_plan(django_user_model):
    user = django_user_model.objects.create_user(
        username="pro_user",
        email="pro@example.com",
        password="StrongPass123!",
    )

    quota = user.variant_quota  # ✅ already exists
    quota.plan = "pro"
    quota.subscription_expires = timezone.now() + timedelta(days=30)
    quota.count = 0
    quota.custom_limit = None
    quota.save()

    return user


@pytest.fixture
def user_with_enterprise_plan(django_user_model):
    user = django_user_model.objects.create_user(
        username="enterprise_user",
        email="enterprise@example.com",
        password="StrongPass123!",
    )

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