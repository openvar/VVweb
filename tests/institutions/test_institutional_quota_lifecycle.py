import pytest
from django.utils import timezone
from datetime import timedelta

from web.models import (
    Institution,
    InstitutionMembership,
    VariantQuota,
)


@pytest.mark.django_db
def test_institutional_quota_lifecycle_with_verified_user(
    client,
    standard_user,
    verify_email,
    submit_verification_form,
):
    """
    End-to-end institutional lifecycle test with APPROVED verification.

    Covers:
    - Standard user baseline quota
    - Institutional uplift (requires verified user)
    - Membership removal fallback
    - Re-application of institutional uplift
    - Institution expiry fallback
    """

    # ------------------------------------------------------
    # LOGIN + VERIFICATION SUBMISSION
    # ------------------------------------------------------
    client.force_login(standard_user)
    verify_email(standard_user)
    submit_verification_form()

    # ------------------------------------------------------
    # SIMULATE APPROVED VERIFICATION (REQUIRED FOR UPLIFT)
    # ------------------------------------------------------
    profile = standard_user.profile
    profile.verification_status = "verified"
    profile.save(update_fields=["verification_status"])

    # Confirm state
    profile.refresh_from_db()
    assert profile.verification_status == "verified"

    quota = VariantQuota.objects.get(user=standard_user)
    default_allowance = quota.effective_allowance
    assert default_allowance > 0

    # ------------------------------------------------------
    # Create active institution
    # ------------------------------------------------------
    institution = Institution.objects.create(
        name="Test University",
        active=True,
        variant_limit=10000,
    )

    # ------------------------------------------------------
    # Add user to institution
    # ------------------------------------------------------
    InstitutionMembership.objects.create(
        user=standard_user,
        institution=institution,
        source="manual",
        active=True,
        verified_at=timezone.now(),
    )

    quota.institution = institution
    quota.save()
    quota.refresh_from_db()

    # Institutional uplift must apply
    assert quota.effective_allowance == institution.variant_limit

    # ------------------------------------------------------
    # Remove user from institution
    # ------------------------------------------------------
    quota.institution = None
    quota.save()
    quota.refresh_from_db()

    assert quota.effective_allowance == default_allowance

    # ------------------------------------------------------
    # Re-add user to institution
    # ------------------------------------------------------
    quota.institution = institution
    quota.save()
    quota.refresh_from_db()

    assert quota.effective_allowance == institution.variant_limit

    # ------------------------------------------------------
    # Expire institution subscription
    # ------------------------------------------------------
    institution.subscription_expires = timezone.now() - timedelta(days=1)
    institution.save()

    quota.refresh_from_db()
    assert not institution.is_active

    # Uplift must be removed automatically
    assert quota.effective_allowance == default_allowance

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
