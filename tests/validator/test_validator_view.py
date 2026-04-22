import pytest
from django.urls import reverse


VALID_VARIANT = "NC_000017.11:g.50198002C>A"

WARNING_TEXT = "Warning: Only"
LOCKED_TEXT = "to continue"


def _post_validate(client, variant=VALID_VARIANT):
    """
    POST helper for validation.
    We do not follow redirects; we inspect the rendered HTML directly.
    """
    return client.post(
        reverse("validate"),
        data={
            "variant": variant,
            "genomebuild": "GRCh38",
            "refsource": "refseq",
            "transcripts": "mane_select",
            "pdf_request": "False",
        },
        follow=False,
    )


@pytest.mark.django_db
def test_anon_user_sees_warning_banner_on_get_under_limit(client):
    """
    Anonymous users under the limit see a WARNING banner on GET.
    This matches the real UX before exhaustion.
    """

    response = client.get(reverse("validate"))
    assert response.status_code == 200

    html = response.content.decode("utf-8")

    assert WARNING_TEXT in html
    assert LOCKED_TEXT not in html


@pytest.mark.django_db
def test_anon_user_sees_warning_banner_up_to_limit(client):
    """
    Anonymous users continue to see the WARNING banner
    while still under the limit.
    """

    for _ in range(4):
        _post_validate(client)

    response = client.get(reverse("validate"))
    assert response.status_code == 200

    html = response.content.decode("utf-8")

    assert WARNING_TEXT in html
    assert LOCKED_TEXT not in html


@pytest.mark.django_db
def test_anon_user_sees_lockout_banner_on_get_after_exhaustion(client):
    """
    After exhaustion, a GET shows the lockout banner.
    This matches the post-exhaustion screenshot exactly.
    """

    sess = client.session
    sess["validations"] = 5
    sess.save()

    response = client.get(reverse("validate"))
    assert response.status_code == 200

    html = response.content.decode("utf-8")

    assert LOCKED_TEXT in html
    assert WARNING_TEXT not in html


@pytest.mark.django_db
def test_anon_user_is_blocked_on_post_after_exhaustion(client):
    """
    After exhaustion, POST is blocked (enforced),
    and the lockout message is shown.
    """

    sess = client.session
    sess["validations"] = 5
    sess.save()

    response = _post_validate(client)
    assert response.status_code == 200

    html = response.content.decode("utf-8")

    assert LOCKED_TEXT in html
    assert WARNING_TEXT not in html


@pytest.mark.django_db
def test_logged_in_user_never_sees_anon_warning_or_lockout(
    client,
    standard_user,
    verify_email,
    submit_verification_form,
):
    """
    Logged-in users are not subject to anonymous limits.
    No warning or lockout banners should appear on GET or POST.
    """

    client.force_login(standard_user)
    verify_email(standard_user)
    submit_verification_form()

    response = client.get(reverse("validate"))
    assert response.status_code == 200

    html = response.content.decode("utf-8")
    assert WARNING_TEXT not in html
    assert LOCKED_TEXT not in html

    response = _post_validate(client)
    assert response.status_code == 200

    html = response.content.decode("utf-8")
    assert WARNING_TEXT not in html
    assert LOCKED_TEXT not in html

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
