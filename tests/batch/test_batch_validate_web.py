
import pytest
from django.urls import reverse
from django.contrib.messages import get_messages


@pytest.mark.django_db
def test_logged_in_user_can_submit_batch_job(
    client,
    standard_user,
    verify_email,
    submit_verification_form,
):
    """
    Stage 1 batch validator web test:

    - User is logged in
    - User email is verified (allauth)
    - User has passed VV verification gate (/verify/)
    - Batch form renders correctly
    - Valid HGVS batch submission succeeds
    - User is redirected back with a success message containing a Job ID
    """

    # ------------------------------------------------------------------
    # Arrange
    # ------------------------------------------------------------------

    client.force_login(standard_user)
    verify_email(standard_user)
    submit_verification_form()   # ✅ CORRECT

    url = reverse("batch_validate")

    post_data = {
        "input_variants": "NC_000017.11:g.50198002C>A",
        "gene_symbols": "",
        "select_transcripts": "mane_select",
        "options": [],
        "verified_email": standard_user.email,
        "genome": "GRCh38",
        "refsource": "refseq",
    }

    # ------------------------------------------------------------------
    # Act — GET
    # ------------------------------------------------------------------

    response_get = client.get(url)

    assert response_get.status_code == 200
    assert "form" in response_get.context
    assert response_get.context["locked"] is False

    # ------------------------------------------------------------------
    # Act — POST
    # ------------------------------------------------------------------

    response_post = client.post(url, data=post_data, follow=False)

    assert response_post.status_code == 302
    assert response_post["Location"].endswith(url)

    response_follow = client.get(url)
    messages = list(get_messages(response_follow.wsgi_request))

    assert any(
        m.level_tag == "success" and "Job ID" in str(m.message)
        for m in messages
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
