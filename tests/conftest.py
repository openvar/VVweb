# tests/conftest.py

import pytest
from datetime import timedelta

from django.conf import settings
from django.test import Client
from django.utils import timezone
from django.contrib.auth import get_user_model

from allauth.account.models import EmailAddress
from userprofiles.models import ORG_TYPES

User = get_user_model()


# ==========================================================
# CLIENT
# ==========================================================

@pytest.fixture
def client():
    """
    Django test client with a final hard stop if the production
    database is ever selected.
    """
    if settings.DATABASES["default"]["NAME"] == "vvweb":
        raise RuntimeError(
            "FATAL: Django is pointing at the production database (vvweb)"
        )
    return Client()


# ==========================================================
# EMAIL VERIFICATION
# ==========================================================

@pytest.fixture
def verify_email(db):
    """
    Mark the user's primary email as verified.
    Keeps allauth + UserProfile state in sync.
    """
    def _verify(user):
        EmailAddress.objects.get_or_create(
            user=user,
            email=user.email,
            defaults={
                "primary": True,
                "verified": True,
            },
        )

        profile = user.profile
        profile.email_is_verified = True
        profile.update_completion_level()
        profile.save()

    return _verify


# ==========================================================
# VERIFICATION FORM
# ==========================================================

@pytest.fixture
def submit_verification_form(client, db):
    def _submit(org_type=None, finalize=True):
        if org_type is None:
            org_type = next(
                key for key, _ in ORG_TYPES
                if key and not key.startswith("commercial")
            )

        response = client.post(
            "/verify/",
            data={
                "org_type": org_type,
                "country": "GB",
                "accept_terms": True,
            },
            follow=False,
        )

        user_id = client.session.get("_auth_user_id")
        assert user_id, "submit_verification_form() called without login"

        user = User.objects.get(pk=user_id)
        profile = user.profile
        profile.refresh_from_db()

        assert profile.terms_accepted_at is not None

        # ✅ only auto-finalise when the test expects it
        if finalize and profile.verification_status in ("not_started", "pending"):
            profile.verification_status = "verified"
            profile.verified_at = timezone.now()
            profile.save(update_fields=["verification_status", "verified_at"])

        return response

    return _submit


# ==========================================================
# USER CREATION HELPER (INTERNAL)
# ==========================================================

def _get_or_create_user(
    django_user_model,
    *,
    username,
    email,
    password,
):
    """
    Idempotent user factory for long-running / reused test databases.
    """
    user, _ = django_user_model.objects.get_or_create(
        username=username,
        defaults={"email": email},
    )

    # Always normalize password + activation
    user.email = email
    user.is_active = True
    user.set_password(password)
    user.save()

    return user


# ==========================================================
# QUOTA FIXTURES — NON‑COMMERCIAL USERS
# ==========================================================

@pytest.fixture
def standard_user(django_user_model):
    """
    Normal user with the default STANDARD plan.
    """
    user = _get_or_create_user(
        django_user_model,
        username="standard_user",
        email="standard@example.com",
        password="StrongPass123!",
    )

    quota = user.variant_quota
    quota.plan = "standard"
    quota.subscription_expires = None
    quota.custom_limit = None
    quota.save()

    return user


@pytest.fixture
def user_with_pro_plan(django_user_model):
    user = _get_or_create_user(
        django_user_model,
        username="pro_user",
        email="pro@example.com",
        password="StrongPass123!",
    )

    quota = user.variant_quota
    quota.plan = "pro"
    quota.subscription_expires = timezone.now() + timedelta(days=30)
    quota.save()

    return user


@pytest.fixture
def user_with_enterprise_plan(django_user_model):
    user = _get_or_create_user(
        django_user_model,
        username="enterprise_user",
        email="enterprise@example.com",
        password="StrongPass123!",
    )

    quota = user.variant_quota
    quota.plan = "enterprise"
    quota.subscription_expires = timezone.now() + timedelta(days=30)
    quota.save()

    return user


# ==========================================================
# QUOTA FIXTURES — COMMERCIAL USERS
# ==========================================================

@pytest.fixture
def commercial_user(django_user_model):
    """
    Commercial user with the default COMMERCIAL plan.
    """
    user = _get_or_create_user(
        django_user_model,
        username="commercial_user",
        email="commercial@example.com",
        password="StrongPass123!",
    )

    profile = user.profile
    profile.verification_status = "commercial"
    profile.save(update_fields=["verification_status"])

    quota = user.variant_quota
    quota.plan = "commercial"
    quota.subscription_expires = None
    quota.custom_limit = None
    quota.save()

    return user


@pytest.fixture
def commercial_user_with_pro_plan(django_user_model):
    user = _get_or_create_user(
        django_user_model,
        username="commercial_pro_user",
        email="commercial_pro@example.com",
        password="StrongPass123!",
    )

    profile = user.profile
    profile.verification_status = "commercial"
    profile.save(update_fields=["verification_status"])

    quota = user.variant_quota
    quota.plan = "pro"
    quota.subscription_expires = timezone.now() + timedelta(days=30)
    quota.save()

    return user


@pytest.fixture
def commercial_user_with_enterprise_plan(django_user_model):
    user = _get_or_create_user(
        django_user_model,
        username="commercial_enterprise_user",
        email="commercial_enterprise@example.com",
        password="StrongPass123!",
    )

    profile = user.profile
    profile.verification_status = "commercial"
    profile.save(update_fields=["verification_status"])

    quota = user.variant_quota
    quota.plan = "enterprise"
    quota.subscription_expires = timezone.now() + timedelta(days=30)
    quota.save()

    return user


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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
# </LICENSE>
