import pytest
from django.urls import reverse

from VVweb.web.models import VariantQuota


@pytest.mark.django_db
def test_validator_does_not_consume_quota_on_validation_exception(
    client,
    standard_user,
    verify_email,
    submit_verification_form,
    monkeypatch,
):
    """
    If the validator crashes internally (exception during validation),
    the error path must be taken and quota must NOT be deducted.

    This simulates an internal VV failure that is caught by the view
    (i.e. NOT an HTTP 500), which is the intended behaviour.
    """

    # -------------------------------------------------------
    # Setup: logged-in, fully verified user
    # -------------------------------------------------------
    client.force_login(standard_user)
    verify_email(standard_user)
    submit_verification_form()

    profile = standard_user.profile
    profile.verification_status = "verified"
    profile.save(update_fields=["verification_status"])

    quota = VariantQuota.objects.get(user=standard_user)
    quota.refresh_from_db()
    initial_count = quota.count

    # -------------------------------------------------------
    # Force an exception inside the validator
    # -------------------------------------------------------
    def explode(*args, **kwargs):
        raise RuntimeError("Simulated internal validator crash")

    # Patch the validator returned by the object pool
    monkeypatch.setattr(
        "VVweb.web.views.vval_object_pool.get_object",
        lambda: type(
            "ExplodingValidator",
            (),
            {
                "validate": explode,
            },
        )()
    )

    # -------------------------------------------------------
    # Perform request (exception is handled → HTTP 200)
    # -------------------------------------------------------
    response = client.post(
        reverse("validate"),
        data={
            "variant": "NM_000088.4:c.589G>T",
            "genomebuild": "GRCh38",
            "refsource": "refseq",
            "transcripts": "all",
        },
        follow=False,
    )

    # The view is designed to catch validator exceptions
    assert response.status_code == 200

    # Optional sanity: error content rendered
    assert b"error" in response.content.lower()

    # -------------------------------------------------------
    # Assert: quota was NOT consumed
    # -------------------------------------------------------
    quota.refresh_from_db()
    assert quota.count == initial_count, (
        "Quota was deducted despite validator failing before successful completion"
    )

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
