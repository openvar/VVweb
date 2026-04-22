import pytest
from django.urls import reverse

from web.models import VariantQuota


@pytest.mark.django_db
def test_batch_submission_rejected_when_quota_exhausted(
    client,
    standard_user,
    verify_email,
    submit_verification_form,
    monkeypatch,
):
    """
    Consecutive batch submissions must be rejected once
    the user's quota is exhausted.
    """

    # -----------------------------------
    # Setup verified user with small quota
    # -----------------------------------
    client.force_login(standard_user)
    verify_email(standard_user)
    submit_verification_form()

    profile = standard_user.profile
    profile.verification_status = "verified"
    profile.save(update_fields=["verification_status"])

    quota = VariantQuota.objects.get(user=standard_user)
    quota.reset_if_needed()

    # Force a very small quota to make exhaustion deterministic
    quota.custom_limit = 5
    quota.save(update_fields=["custom_limit"])

    start_count = quota.count

    # -----------------------------------
    # Prevent Celery routing (view-level test)
    # -----------------------------------
    monkeypatch.setattr(
        "web.views.tasks.batch_validate.delay",
        lambda **kwargs: "FAKE-JOB-ID"
    )

    # Helper payload
    variants = "\n".join(["NM_000088.4:c.589G>T"] * 5)

    payload = {
        "input_variants": variants,
        "verified_email": standard_user.email,
        "genome": "GRCh38",
        "refsource": "refseq",
        "gene_symbols": "",
        "select_transcripts": "mane_select",
        "options": [],
    }

    # -----------------------------------
    # First submission: should succeed
    # -----------------------------------
    response1 = client.post(
        reverse("batch_validate"),
        data=payload,
        follow=True,
    )

    assert response1.status_code == 200

    quota.refresh_from_db()
    assert quota.count == start_count + 5
    assert quota.remaining == 0

    # -----------------------------------
    # Second submission: should be REJECTED
    # -----------------------------------
    response2 = client.post(
        reverse("batch_validate"),
        data=payload,
        follow=True,
    )

    assert response2.status_code == 200

    # Should NOT increase quota
    quota.refresh_from_db()
    assert quota.count == start_count + 5

    # Should show quota error to user
    html = response2.content.decode("utf-8")
    assert "insufficient quota" in html.lower() or "monthly" in html.lower()

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

