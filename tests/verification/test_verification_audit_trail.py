import pytest
from django.utils import timezone
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
def test_audit_fields_set_on_verification(
    client, verify_email, submit_verification_form
):
    admin = User.objects.create_superuser(
        username="admin",
        email="admin@example.com",
        password="AdminPass123!",
    )

    user = User.objects.create_user(
        username="audited_user",
        email="audit@randomdomain.com",
        password="StrongPass123!",
    )

    verify_email(user)
    client.login(username=user.username, password="StrongPass123!")
    submit_verification_form()

    profile = user.profile
    profile.verification_status = "verified"
    profile.verified_by = admin
    profile.verified_at = timezone.now()
    profile.save()

    profile.refresh_from_db()

    assert profile.verification_status == "verified"
    assert profile.verified_by == admin
    assert profile.verified_at is not None

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