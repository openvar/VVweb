import pytest
from django.urls import reverse

from VVweb.web.models import VariantQuota


@pytest.mark.django_db
def test_gene2transcripts_does_not_consume_quota_on_exception(
    client,
    standard_user,
    verify_email,
    submit_verification_form,
    monkeypatch,
):
    """
    If gene2transcripts crashes internally, quota must NOT be deducted.
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
    # Force exception inside gene2transcripts task
    # -------------------------------------------------------
    def explode(*args, **kwargs):
        raise RuntimeError("Simulated gene2transcripts crash")

    monkeypatch.setattr(
        "VVweb.web.views.tasks.gene2transcripts",
        explode
    )

    # -------------------------------------------------------
    # Perform request (exception is handled → HTTP 200)
    # -------------------------------------------------------
    response = client.post(
        reverse("genes2trans"),
        data={
            "symbol": "COL5A1",
            "transcripts": "all",
            "refsource": "refseq",
        },
        follow=False,
    )

    assert response.status_code == 200

    # -------------------------------------------------------
    # Assert: quota was NOT consumed
    # -------------------------------------------------------
    quota.refresh_from_db()
    assert quota.count == initial_count, (
        "Quota was deducted despite gene2transcripts crashing"
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
