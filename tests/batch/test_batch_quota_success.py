import pytest
from django.urls import reverse

from VVweb.web.models import VariantQuota


@pytest.mark.django_db
def test_batch_quota_consumed_on_success(
    client,
    standard_user,
    verify_email,
    submit_verification_form,
    monkeypatch,
):
    """
    If a batch job completes successfully,
    the reserved quota must remain consumed.
    """

    # -----------------------------
    # Setup verified user
    # -----------------------------
    client.force_login(standard_user)
    verify_email(standard_user)
    submit_verification_form()

    profile = standard_user.profile
    profile.verification_status = "verified"
    profile.save(update_fields=["verification_status"])

    quota = VariantQuota.objects.get(user=standard_user)
    quota.reset_if_needed()
    start_count = quota.count

    # -----------------------------
    # Fake successful batch task
    # -----------------------------
    def fake_batch_task(**kwargs):
        return {"status": "ok"}

    monkeypatch.setattr(
        "VVweb.web.views.tasks.batch_validate.delay",
        lambda **kwargs: "FAKE-JOB-ID"
    )

    # -----------------------------
    # Submit batch
    # -----------------------------
    variants = "\n".join(["NM_000088.4:c.589G>T"] * 5)

    response = client.post(
        reverse("batch_validate"),
        data={
            "input_variants": variants,
            "verified_email": standard_user.email,
            "genome": "GRCh38",
            "refsource": "refseq",
            "gene_symbols": "",
            "select_transcripts": "mane_select",
            "options": [],
        },
        follow=True,
    )

    assert response.status_code == 200

    # -----------------------------
    # Assert quota consumed
    # -----------------------------
    quota.refresh_from_db()
    assert quota.count == start_count + 5

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
