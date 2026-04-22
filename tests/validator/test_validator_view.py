import pytest
from django.urls import reverse


VALID_VARIANT = "NC_000017.11:g.50198002C>A"


def _post_validate(client, variant=VALID_VARIANT):
    """
    Helper to POST to the validate endpoint.
    """
    return client.post(
        reverse("validate"),
        data={
            "variant": variant,
            "genomebuild": "GRCh38",
            "refsource": "refseq",
            "transcripts": "mane_select",
        },
        follow=True,
    )


@pytest.mark.django_db
def test_anonymous_user_can_validate_five_times(client):
    """
    Anonymous users are allowed exactly 5 validations.
    """

    # Perform 5 validations
    for i in range(5):
        response = _post_validate(client)

        # Validation should be performed
        assert response.status_code == 200
        assert response.context["output"] is not None
        assert response.context.get("locked") is not True

        # Session counter increments
        assert client.session.get("validations") == i + 1


@pytest.mark.django_db
def test_sixth_anonymous_validation_is_blocked(client):
    """
    Sixth anonymous validation attempt is blocked.
    """

    # Burn through the 5 allowed validations
    for _ in range(5):
        _post_validate(client)

    # Sixth attempt
    response = _post_validate(client)

    assert response.status_code == 200

    # Validation should NOT be performed
    assert response.context["output"] is None
    assert response.context["locked"] is True

    # Counter must not increment past 5
    assert client.session.get("validations") == 5


@pytest.mark.django_db
def test_logged_in_user_can_validate(client, standard_user, verify_email, submit_verification_form):
    """
    Logged-in users are not subject to anonymous validation limits.
    """

    client.force_login(standard_user)
    verify_email(standard_user)
    submit_verification_form()

    response = _post_validate(client)

    assert response.status_code == 200

    # Validation should succeed
    assert response.context["output"] is not None
    assert response.context.get("locked") is not True

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
