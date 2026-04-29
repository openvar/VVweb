import pytest
from django.urls import reverse

from VVweb.web.models import VariantQuota
from VVweb.web import tasks


@pytest.mark.django_db
def test_batch_quota_rolled_back_on_task_failure(
    client,
    standard_user,
    verify_email,
    submit_verification_form,
    monkeypatch,
):
    """
    If batch validation crashes in the worker,
    quota reservation must be rolled back.

    This test intercepts exactly one pool checkout
    without modifying pool contents or global state.
    """

    # -------------------------------------------------
    # Arrange — verified user
    # -------------------------------------------------
    client.force_login(standard_user)
    verify_email(standard_user)
    submit_verification_form()

    profile = standard_user.profile
    profile.verification_status = "verified"
    profile.save(update_fields=["verification_status"])

    quota = VariantQuota.objects.get(user=standard_user)
    quota.reset_if_needed()
    start_count = quota.count

    # -------------------------------------------------
    # Submit batch (reservation happens here)
    # -------------------------------------------------
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

    quota.refresh_from_db()
    assert quota.count == start_count + 5

    # -------------------------------------------------
    # Intercept exactly ONE validator checkout
    # -------------------------------------------------
    pool = tasks.batch_object_pool
    original_get_object = pool.get_object

    exploding_validator = original_get_object()
    assert exploding_validator is not None

    def exploding_validate(*args, **kwargs):
        raise RuntimeError("Simulated worker crash")

    monkeypatch.setattr(exploding_validator, "validate", exploding_validate)

    used = False

    def controlled_get_object():
        nonlocal used
        if not used:
            used = True
            return exploding_validator
        return original_get_object()

    monkeypatch.setattr(pool, "get_object", controlled_get_object)

    try:
        # -------------------------------------------------
        # Execute task directly
        # -------------------------------------------------
        with pytest.raises(RuntimeError):
            tasks.batch_validate(
                variant="V|V|V|V|V",
                genome="GRCh38",
                email=standard_user.email,
                gene_symbols="",
                transcripts="mane_select",
                user_id=standard_user.id,
                reserved_n=5,
            )
    finally:
        # Ensure the validator is returned to the pool
        pool.return_object(exploding_validator)

    # -------------------------------------------------
    # Assert quota rolled back
    # -------------------------------------------------
    quota.refresh_from_db()
    assert quota.count == start_count

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
