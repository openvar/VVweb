import re
import time
from pathlib import Path

import pytest
from django.urls import reverse
from django.contrib.messages import get_messages


@pytest.mark.django_db(transaction=True)
def test_batch_manual_file_input(
    client,
    standard_user,
    verify_email,
    submit_verification_form,
):
    """
    Manual, file-driven batch test.

    Behaviour:
      - Reads batch_testing/input.txt
      - Requests FULL output schema via options
      - Triggers real VV batch execution (Celery bypassed in tests)
      - Polls /batch_validate until Job ID appears
      - Hard abort after 1 hour if batch never completes
      - Downloads results via REAL batch_download route
      - Verifies full header and row-width consistency

    This mirrors real production semantics for large batches.
    """

    # ------------------------------------------------------------------
    # Paths
    # ------------------------------------------------------------------
    project_root = Path(__file__).resolve().parents[2]
    batch_dir = project_root / "batch_testing"
    input_path = batch_dir / "input.txt"
    output_path = batch_dir / "output.txt"

    # ------------------------------------------------------------------
    # Opt-in behaviour
    # ------------------------------------------------------------------
    if not input_path.exists():
        pytest.skip("batch_testing/input.txt not present – manual batch test skipped")

    input_variants = input_path.read_text().strip()
    if not input_variants:
        pytest.skip("batch_testing/input.txt is empty – manual batch test skipped")

    # ------------------------------------------------------------------
    # Setup user + session
    # ------------------------------------------------------------------
    client.force_login(standard_user)
    verify_email(standard_user)
    submit_verification_form()

    batch_url = reverse("batch_validate")

    # ------------------------------------------------------------------
    # IMPORTANT: request FULL output schema
    # ------------------------------------------------------------------
    post_data = {
        "input_variants": input_variants,
        "gene_symbols": "",
        "select_transcripts": "mane_select",
        "options": [
            "transcript",
            "genomic",
            "protein",
            "refseqgene",
            "lrg",
            "vcf",
            "gene_info",
            "tx_name",
            "alt_loci",
        ],
        "verified_email": standard_user.email,
        "genome": "GRCh38",
        "refsource": "refseq",
    }

    # ------------------------------------------------------------------
    # Submit batch (staging only)
    # ------------------------------------------------------------------
    response = client.post(batch_url, data=post_data, follow=False)
    assert response.status_code in (200, 302)

    # ------------------------------------------------------------------
    # WAIT FOR BATCH COMPLETION
    # ------------------------------------------------------------------
    job_id = None
    start_time = time.monotonic()
    deadline = start_time + 3600  # 1 hour hard cutoff

    print(">>> Waiting for batch completion (up to 1 hour)")

    while time.monotonic() < deadline:
        response = client.get(batch_url)
        messages = list(get_messages(response.wsgi_request))

        for msg in messages:
            match = re.search(r"Job ID:\s*([a-f0-9-]+)", str(msg.message))
            if match:
                job_id = match.group(1)
                break

        if job_id:
            print(f">>> Batch completed, Job ID = {job_id}")
            break

        elapsed = int(time.monotonic() - start_time)
        print(f">>> Batch still running… {elapsed}s elapsed")
        time.sleep(5)

    assert job_id, "Job ID missing from success message after 1 hour wait"

    # ------------------------------------------------------------------
    # Download results via REAL route
    # ------------------------------------------------------------------
    download_url = reverse("batch_download", args=[job_id])
    response = client.get(download_url)

    assert response.status_code == 200
    assert "attachment" in response["Content-Disposition"]
    assert job_id in response["Content-Disposition"]

    # Persist artefact for inspection
    output_path.write_bytes(response.content)

    # ------------------------------------------------------------------
    # Structural assertions
    # ------------------------------------------------------------------
    content = response.content.decode(errors="replace")
    lines = [l for l in content.splitlines() if l.strip()]

    assert "# ERROR: Failed to process results." not in content
    assert any(l.startswith("# Metadata:") for l in lines)
    assert any(l.startswith("# Job ID:") for l in lines)

    # ------------------------------------------------------------------
    # Full header verification
    # ------------------------------------------------------------------
    table_lines = [l for l in lines if not l.startswith("#")]
    assert table_lines, "No tabular output found"

    header = table_lines[0]
    header_fields = header.split("\t")

    EXPECTED_HEADER_FIELDS = [
        "Input",
        "Warnings",
        "Select transcript",
        "HGVS_transcript",
        "HGVS_intronic_chr_context",
        "HGVS_intronic_rsg_context",
        "HGVS_RefSeqGene",
        "HGVS_LRG",
        "HGVS_LRG_transcript",
        "HGVS_Predicted_Protein",
        "HGVS_Genomic_GRCh37",
        "HGVS_Genomic_GRCh38",
        "GRCh37_CHR",
        "GRCh37_POS",
        "GRCh37_ID",
        "GRCh37_REF",
        "GRCh37_ALT",
        "GRCh38_CHR",
        "GRCh38_POS",
        "GRCh38_ID",
        "GRCh38_REF",
        "GRCh38_ALT",
        "Gene_Symbol",
        "HGNC_Gene_ID",
        "Transcript_description",
        "Alt_genomic_loci",
    ]

    assert header_fields == EXPECTED_HEADER_FIELDS, (
        f"Header mismatch.\nExpected: {EXPECTED_HEADER_FIELDS}\nGot: {header_fields}"
    )

    # ------------------------------------------------------------------
    # Row width consistency
    # ------------------------------------------------------------------
    for row in table_lines[1:]:
        fields = row.split("\t")
        assert len(fields) == len(EXPECTED_HEADER_FIELDS), (
            "Data row does not match declared header width"
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
