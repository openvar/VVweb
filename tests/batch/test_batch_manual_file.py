import re
from pathlib import Path

import pytest
from django.urls import reverse
from django_celery_results.models import TaskResult


@pytest.mark.django_db(transaction=True)
def test_batch_manual_file_input(
    client,
    standard_user,
    verify_email,
    submit_verification_form,
):
    """
    Manual, file-driven end-to-end batch test.

    - Reads batch_testing/input.txt
    - Writes batch_testing/output.txt
    - Runs under pytest with eager Celery
    - Uses real web views
    - DOES NOT rely on UI messages
    - Extracts Job ID from TaskResult (eager-safe)
    - Asserts ONLY invariant structure:
        * '# Metadata:' line exists
        * '# Job ID:' line exists
        * Exact header row exists

    No assertions on variant content.
    """

    # --------------------------------------------------
    # Paths
    # --------------------------------------------------
    project_root = Path(__file__).resolve().parents[2]
    batch_dir = project_root / "batch_testing"
    input_path = batch_dir / "input.txt"
    output_path = batch_dir / "output.txt"

    # --------------------------------------------------
    # Fail-safe: skip if input not provided
    # --------------------------------------------------
    if not input_path.exists():
        pytest.skip(
            "batch_testing/input.txt not present – manual batch test skipped"
        )

    input_variants = input_path.read_text().strip()
    if not input_variants:
        pytest.skip(
            "batch_testing/input.txt is empty – manual batch test skipped"
        )

    # --------------------------------------------------
    # Setup user + session
    # --------------------------------------------------
    client.force_login(standard_user)
    verify_email(standard_user)
    submit_verification_form()

    batch_url = reverse("batch_validate")

    post_data = {
        "input_variants": input_variants,
        "gene_symbols": "",
        "select_transcripts": "mane_select",
        "options": [],
        "verified_email": standard_user.email,
        "genome": "GRCh38",
        "refsource": "refseq",
    }

    # --------------------------------------------------
    # Submit batch job
    # --------------------------------------------------
    response = client.post(batch_url, data=post_data, follow=False)

    # In eager mode, batch completes inline.
    # View may return 200 or 302 depending on path.
    assert response.status_code in (200, 302), (
        f"Unexpected status code on batch submit: {response.status_code}"
    )

    # --------------------------------------------------
    # Obtain Job ID from TaskResult (eager-safe)
    # --------------------------------------------------
    task = (
        TaskResult.objects
        .filter(task_name__icontains="batch")
        .order_by("-date_done")
        .first()
    )

    assert task is not None, "No TaskResult created by batch job"
    job_id = task.task_id

    # --------------------------------------------------
    # Download results
    # --------------------------------------------------
    download_url = reverse("batch_download", args=[job_id])
    response = client.get(download_url)

    assert response.status_code == 200
    assert "attachment" in response["Content-Disposition"]
    assert job_id in response["Content-Disposition"]

    # Write output artefact
    output_path.write_bytes(response.content)

    # --------------------------------------------------
    # Structural assertions only (stable guarantees)
    # --------------------------------------------------
    content = response.content.decode(errors="replace")
    lines = [l for l in content.splitlines() if l.strip()]

    # Must not hit generic downloader failure
    assert "# ERROR: Failed to process results." not in content

    # Metadata line must exist
    assert any(
        l.startswith("# Metadata:")
        for l in lines
    ), "Missing '# Metadata:' line"

    # Job ID line must exist
    assert any(
        l.startswith("# Job ID:")
        for l in lines
    ), "Missing '# Job ID:' line"

    # Exact header row (schema invariant)
    EXPECTED_HEADER = (
        "Input\tWarnings\tSelect transcript\tHGVS_transcript\t"
        "HGVS_intronic_chr_context\tHGVS_intronic_rsg_context\t"
        "HGVS_RefSeqGene\tHGVS_LRG\tHGVS_LRG_transcript\t"
        "HGVS_Predicted_Protein\tHGVS_Genomic_GRCh37\t"
        "HGVS_Genomic_GRCh38\tGRCh37_CHR\tGRCh37_POS\t"
        "GRCh37_ID\tGRCh37_REF\tGRCh37_ALT\t"
        "GRCh38_CHR\tGRCh38_POS\tGRCh38_ID\t"
        "GRCh38_REF\tGRCh38_ALT\tGene_Symbol\tHGNC_Gene_ID"
    )

    assert EXPECTED_HEADER in lines, "Expected header row not found"

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
