import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_genes2transcripts_end_to_end_col5a1_multiple_and_mane_select(
    client,
    standard_user,
    verify_email,
    submit_verification_form,
):
    """
    End-to-end test for the Gene → Transcripts service using COL5A1.

    Guarantees tested:
    - Logged-in, verified user can access the service
    - Real gene2transcripts lookup is performed
    - More than one transcript is returned (select_transcripts=all)
    - At least one transcript is MANE Select
    """

    # ----------------------------------------------------------
    # Arrange: logged-in, verified user
    # ----------------------------------------------------------
    client.force_login(standard_user)
    verify_email(standard_user)
    submit_verification_form()

    url = reverse("genes2trans")

    gene_symbol = "COL5A1"

    # ----------------------------------------------------------
    # Act: submit gene → transcripts request
    # NOTE: select_transcripts MUST be "all" to get >1 transcript
    # ----------------------------------------------------------
    response = client.post(
        url,
        data={
            "symbol": gene_symbol,
            "transcripts": "all",
            "refsource": "refseq",
        },
        follow=True,
    )

    # ----------------------------------------------------------
    # Assert: request succeeded
    # ----------------------------------------------------------
    assert response.status_code == 200
    assert "output" in response.context

    output = response.context["output"]
    assert output is not None, "No output returned from gene2transcripts"

    # ----------------------------------------------------------
    # Assert: output structure
    # ----------------------------------------------------------
    assert "transcripts" in output
    transcripts = output["transcripts"]

    assert isinstance(transcripts, list)
    assert len(transcripts) > 1, (
        "Expected more than one transcript for COL5A1 "
        "when select_transcripts=all"
    )

    # ----------------------------------------------------------
    # Assert: requested and resolved symbols
    # ----------------------------------------------------------
    assert output.get("requested_symbol", "").upper() == gene_symbol
    assert output.get("current_symbol")
    assert output.get("current_name")

    # ----------------------------------------------------------
    # Assert: at least one MANE Select transcript exists
    # ----------------------------------------------------------
    mane_select_transcripts = [
        t for t in transcripts
        if t.get("annotations", {}).get("mane_select") is True
    ]

    assert mane_select_transcripts, (
        "Expected at least one MANE Select transcript for COL5A1"
    )

    # ----------------------------------------------------------
    # Assert: transcript entries are sane
    # ----------------------------------------------------------
    for trans in transcripts:
        assert "reference" in trans
        assert "coding_start" in trans
        assert "coding_end" in trans
        assert "description" in trans
        assert "annotations" in trans
        assert "url" in trans

        assert (
            trans["reference"].startswith("NM_")
            or trans["reference"].startswith("NR_")
            or trans["reference"].startswith("LRG_")
        ), f"Unexpected transcript accession: {trans['reference']}"

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
