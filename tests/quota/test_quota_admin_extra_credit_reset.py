import pytest
from datetime import timedelta
from django.utils import timezone
from django.conf import settings


@pytest.mark.django_db
def test_admin_extra_credit_wiped_after_month_standard_user(
    user_with_pro_plan
):
    """
    Admin adds extra credit to a STANDARD user.
    After one month the credit is wiped.
    The plan remains STANDARD.
    """
    user = user_with_pro_plan
    quota = user.variant_quota

    # --- Normalize to STANDARD base plan ---
    quota.plan = "standard"
    quota.subscription_expires = None
    quota.custom_limit = None
    quota.last_reset = timezone.now()
    quota.save(
        update_fields=[
            "plan",
            "subscription_expires",
            "custom_limit",
            "last_reset",
        ]
    )

    quota.refresh_from_db()

    # ✅ Base allowance BEFORE admin credit
    assert quota.personal_allowance == settings.DEFAULT_MONTHLY_VARIANT_ALLOWANCE
    assert quota.effective_allowance == settings.DEFAULT_MONTHLY_VARIANT_ALLOWANCE

    # --- Admin adds extra credit ---
    quota.custom_limit = 500
    quota.save(update_fields=["custom_limit"])
    quota.refresh_from_db()

    # ✅ Allowance overridden by credit
    assert quota.custom_limit == 500
    assert quota.personal_allowance == 500
    assert quota.effective_allowance == 500

    # --- Simulate one month passing ---
    quota.last_reset = timezone.now() - timedelta(days=31)
    quota.save(update_fields=["last_reset"])

    # --- Trigger monthly reset ---
    quota.reset_if_needed()
    quota.refresh_from_db()

    # ✅ Allowance restored
    assert quota.plan == "standard"
    assert quota.custom_limit is None
    assert quota.personal_allowance == settings.DEFAULT_MONTHLY_VARIANT_ALLOWANCE
    assert quota.effective_allowance == settings.DEFAULT_MONTHLY_VARIANT_ALLOWANCE


@pytest.mark.django_db
def test_admin_extra_credit_wiped_after_month_commercial_user(
    commercial_user_with_pro_plan
):
    """
    Admin adds extra credit to a COMMERCIAL user.
    After one month the credit is wiped.
    The plan remains COMMERCIAL.
    """
    user = commercial_user_with_pro_plan
    profile = user.profile
    quota = user.variant_quota

    # --- Normalize to COMMERCIAL base plan ---
    profile.verification_status = "commercial"
    profile.save(update_fields=["verification_status"])

    quota.plan = "commercial"
    quota.subscription_expires = None
    quota.custom_limit = None
    quota.last_reset = timezone.now()
    quota.save(
        update_fields=[
            "plan",
            "subscription_expires",
            "custom_limit",
            "last_reset",
        ]
    )

    quota.refresh_from_db()

    # ✅ Base allowance BEFORE admin credit
    assert quota.personal_allowance == settings.COMMERCIAL_TRIAL_LIMIT
    assert quota.effective_allowance == settings.COMMERCIAL_TRIAL_LIMIT

    # --- Admin adds extra credit ---
    quota.custom_limit = 1000
    quota.save(update_fields=["custom_limit"])
    quota.refresh_from_db()

    # ✅ Allowance overridden by credit
    assert quota.custom_limit == 1000
    assert quota.personal_allowance == 1000
    assert quota.effective_allowance == 1000

    # --- Simulate one month passing ---
    quota.last_reset = timezone.now() - timedelta(days=31)
    quota.save(update_fields=["last_reset"])

    # --- Trigger monthly reset ---
    quota.reset_if_needed()
    quota.refresh_from_db()

    # ✅ Allowance restored
    assert quota.plan == "commercial"
    assert quota.custom_limit is None
    assert quota.personal_allowance == settings.COMMERCIAL_TRIAL_LIMIT
    assert quota.effective_allowance == settings.COMMERCIAL_TRIAL_LIMIT


@pytest.mark.django_db
def test_admin_extra_credit_wiped_after_month_standard_user(standard_user):
    """
    Admin adds extra credit to a STANDARD user.
    After one month, the credit is wiped.
    The plan remains STANDARD.
    """
    user = standard_user
    quota = user.variant_quota

    # ✅ Base allowance BEFORE admin credit
    assert quota.personal_allowance == settings.DEFAULT_MONTHLY_VARIANT_ALLOWANCE
    assert quota.effective_allowance == settings.DEFAULT_MONTHLY_VARIANT_ALLOWANCE

    # --- Admin adds credit ---
    quota.custom_limit = 500
    quota.last_reset = timezone.now()
    quota.save(update_fields=["custom_limit", "last_reset"])
    quota.refresh_from_db()

    # ✅ Allowance overridden by credit
    assert quota.custom_limit == 500
    assert quota.personal_allowance == 500
    assert quota.effective_allowance == 500

    # --- Simulate one month passing ---
    quota.last_reset = timezone.now() - timedelta(days=31)
    quota.save(update_fields=["last_reset"])

    quota.reset_if_needed()
    quota.refresh_from_db()

    # ✅ Allowance restored
    assert quota.plan == "standard"
    assert quota.custom_limit is None
    assert quota.personal_allowance == settings.DEFAULT_MONTHLY_VARIANT_ALLOWANCE
    assert quota.effective_allowance == settings.DEFAULT_MONTHLY_VARIANT_ALLOWANCE


@pytest.mark.django_db
def test_admin_extra_credit_wiped_after_month_commercial_user(commercial_user):
    """
    Admin adds extra credit to a COMMERCIAL user.
    After one month, the credit is wiped.
    The plan remains COMMERCIAL.
    """
    user = commercial_user
    quota = user.variant_quota
    profile = user.profile

    assert profile.verification_status == "commercial"
    assert quota.plan == "commercial"

    # ✅ Base allowance BEFORE admin credit
    assert quota.personal_allowance == settings.COMMERCIAL_TRIAL_LIMIT
    assert quota.effective_allowance == settings.COMMERCIAL_TRIAL_LIMIT

    # --- Admin adds credit ---
    quota.custom_limit = 1000
    quota.last_reset = timezone.now()
    quota.save(update_fields=["custom_limit", "last_reset"])
    quota.refresh_from_db()

    # ✅ Allowance overridden by credit
    assert quota.custom_limit == 1000
    assert quota.personal_allowance == 1000
    assert quota.effective_allowance == 1000

    # --- Simulate one month passing ---
    quota.last_reset = timezone.now() - timedelta(days=31)
    quota.save(update_fields=["last_reset"])

    quota.reset_if_needed()
    quota.refresh_from_db()

    # ✅ Allowance restored
    assert quota.plan == "commercial"
    assert quota.custom_limit is None
    assert quota.personal_allowance == settings.COMMERCIAL_TRIAL_LIMIT
    assert quota.effective_allowance == settings.COMMERCIAL_TRIAL_LIMIT

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

