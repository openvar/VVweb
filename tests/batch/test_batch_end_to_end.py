import pytest
import re
from django.urls import reverse
from django.contrib.messages import get_messages


@pytest.mark.django_db
def test_batch_job_processes_and_can_be_downloaded_hgvs(
    client,
    standard_user,
    verify_email,
    submit_verification_form,
):
    """
    Phase 2 end-to-end batch workflow test (HGVS input).

    Asserts ONLY hard guarantees made by the current downloader:
    - Batch job executes
    - Result is downloadable
    - No internal error path is hit
    - Job ID line is present
    - If tabular output exists, it is structurally consistent
    - Submitted HGVS variant appears somewhere in data rows
    """

    # ----------------------------------------------------------
    # Setup
    # ----------------------------------------------------------
    client.force_login(standard_user)
    verify_email(standard_user)
    submit_verification_form()

    batch_url = reverse("batch_validate")

    hgvs_variant = "NC_000017.11:g.50198002C>A"

    post_data = {
        "input_variants": hgvs_variant,
        "gene_symbols": "",
        "select_transcripts": "mane_select",
        "options": [],
        "verified_email": standard_user.email,
        "genome": "GRCh38",
        "refsource": "refseq",
    }

    # ----------------------------------------------------------
    # Submit batch job
    # ----------------------------------------------------------
    response = client.post(batch_url, data=post_data, follow=False)
    assert response.status_code == 302

    response = client.get(batch_url)
    messages = list(get_messages(response.wsgi_request))

    job_id = None
    for msg in messages:
        match = re.search(r"Job ID:\s*([a-f0-9-]+)", str(msg.message))
        if match:
            job_id = match.group(1)
            break

    assert job_id, "Job ID missing from success message"

    # ----------------------------------------------------------
    # Download results
    # ----------------------------------------------------------
    download_url = reverse("batch_download", args=[job_id])
    response = client.get(download_url)

    assert response.status_code == 200
    assert "attachment" in response["Content-Disposition"]
    assert job_id in response["Content-Disposition"]

    content = response.content.decode()

    # ----------------------------------------------------------
    # Sanity: downloader must not hit broad exception path
    # ----------------------------------------------------------
    assert "# ERROR: Failed to process results." not in content

    # ----------------------------------------------------------
    # Basic structural assertions
    # ----------------------------------------------------------
    lines = [l for l in content.splitlines() if l.strip()]
    assert any(l.startswith("# Job ID:") for l in lines), "Missing Job ID line"

    # ----------------------------------------------------------
    # Validate tabular output IF present
    # ----------------------------------------------------------
    table_lines = [l for l in lines if not l.startswith("#")]

    if table_lines:
        header = table_lines[0]
        header_fields = header.split("\t")

        assert len(header_fields) > 1, "Header must contain multiple columns"

        for row in table_lines[1:]:
            fields = row.split("\t")

            # Structural consistency
            assert len(fields) == len(header_fields)

            # Semantic: HGVS variant must appear somewhere
            assert any(hgvs_variant in field for field in fields)


@pytest.mark.django_db
def test_batch_job_processes_and_can_be_downloaded_vcf(
    client,
    standard_user,
    verify_email,
    submit_verification_form,
):
    """
    Phase 2 end-to-end batch workflow test (VCF input).

    Caveat:
    - VCF input is tab-delimited
    - Output replaces tabs with commas to preserve tab-delimited output
    - Therefore, a CSV-normalised VCF representation must appear
      somewhere in data rows
    """

    # ----------------------------------------------------------
    # Setup
    # ----------------------------------------------------------
    client.force_login(standard_user)
    verify_email(standard_user)
    submit_verification_form()

    batch_url = reverse("batch_validate")

    # Original VCF (tab-delimited)
    vcf_input = (
        "chr1\t1000000\t.\tN\t<DEL>\t.\tPASS\tSVTYPE=DEL;END=1005000"
    )

    # Expected normalised representation in output (tabs -> commas)
    vcf_csv = (
        "chr1,1000000,.,N,<DEL>,.,PASS,SVTYPE=DEL;END=1005000"
    )

    post_data = {
        "input_variants": vcf_input,
        "gene_symbols": "",
        "select_transcripts": "mane_select",
        "options": [],
        "verified_email": standard_user.email,
        "genome": "GRCh38",
        "refsource": "refseq",
    }

    # ----------------------------------------------------------
    # Submit batch job
    # ----------------------------------------------------------
    response = client.post(batch_url, data=post_data, follow=False)
    assert response.status_code == 302

    response = client.get(batch_url)
    messages = list(get_messages(response.wsgi_request))

    job_id = None
    for msg in messages:
        match = re.search(r"Job ID:\s*([a-f0-9-]+)", str(msg.message))
        if match:
            job_id = match.group(1)
            break

    assert job_id, "Job ID missing from success message"

    # ----------------------------------------------------------
    # Download results
    # ----------------------------------------------------------
    download_url = reverse("batch_download", args=[job_id])
    response = client.get(download_url)

    assert response.status_code == 200
    assert "attachment" in response["Content-Disposition"]
    assert job_id in response["Content-Disposition"]

    content = response.content.decode()

    # ----------------------------------------------------------
    # Sanity: downloader must not hit broad exception path
    # ----------------------------------------------------------
    assert "# ERROR: Failed to process results." not in content

    # ----------------------------------------------------------
    # Basic structural assertions
    # ----------------------------------------------------------
    lines = [l for l in content.splitlines() if l.strip()]
    assert any(l.startswith("# Job ID:") for l in lines), "Missing Job ID line"

    # ----------------------------------------------------------
    # Validate tabular output IF present
    # ----------------------------------------------------------
    table_lines = [l for l in lines if not l.startswith("#")]

    if table_lines:
        header = table_lines[0]
        header_fields = header.split("\t")

        assert len(header_fields) > 1, "Header must contain multiple columns"

        for row in table_lines[1:]:
            fields = row.split("\t")

            # Structural consistency
            assert len(fields) == len(header_fields)

            # Semantic: CSV-normalised VCF input must appear somewhere
            assert any(vcf_csv in field for field in fields)

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
