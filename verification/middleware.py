# verification/middleware.py
from datetime import timedelta

from django.contrib.auth import logout
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone

from allauth.account.models import EmailAddress


class TierEnforcementMiddleware:
    """
    Enforces VariantValidator’s identity, verification and entitlement rules.

    ADDITION: Annual re-validation.
    If terms_accepted_at is None or >= 1 year old:
        The user is reset EXACTLY to a new-account state and forced through
        email confirmation -> verification flow.
    """

    def __init__(self, get_response):
        self.get_response = get_response

        self.allowed_prefixes = [
            "/verify/",
            "/commercial/",
            "/logout/",
            "/accounts/login/",
            "/accounts/logout/",
            "/accounts/signup/",
            "/accounts/confirm-email/",
            "/accounts/email/",
            "/accounts/resend-confirmation/",
            "/static/",
        ]

    def __call__(self, request):

        # Allow logout and admin before enforcement
        if request.path.startswith("/accounts/logout"):
            return self.get_response(request)

        if request.path.startswith("/admin/"):
            return self.get_response(request)

        user = request.user

        if user.is_authenticated:

            # Normalise email always
            if user.email:
                lower = user.email.lower().strip()
                if lower != user.email:
                    user.email = lower
                    user.save(update_fields=["email"])

            profile = getattr(user, "profile", None)
            if profile is None:
                logout(request)
                return redirect(reverse("account_login"))

            # =====================================================================
            # ANNUAL REVALIDATION LOGIC
            # =====================================================================
            needs_reset = False

            if profile.terms_accepted_at is None:
                needs_reset = True
            else:
                one_year_later = profile.terms_accepted_at + timedelta(days=365)
                if timezone.now() >= one_year_later:
                    needs_reset = True

            # Check Allauth email verification state
            email_obj = EmailAddress.objects.filter(
                user=user, email=user.email
            ).first()
            email_verified_now = email_obj.verified if email_obj else False

            if needs_reset:

                # ============================================================
                # Reset profile state to EXACT "new account" condition
                # ============================================================
                profile.email_is_verified = False
                profile.terms_accepted_at = None
                profile.org_type = None
                profile.jobrole = ""
                profile.personal_info_is_completed = False
                profile.completion_level = 0
                profile.verification_status = "not_started"
                profile.verified_at = None
                profile.verified_by = None
                profile.rejection_reason = ""
                profile.save()

                # ============================================================
                # FIX 1 — Ensure Allauth EmailAddress exists + reset verification
                # ============================================================
                email_obj, created = EmailAddress.objects.get_or_create(
                    user=user,
                    email=user.email,
                    defaults={"primary": True, "verified": False},
                )

                # Force "new user" state for Allauth
                email_obj.verified = False
                email_obj.primary = True
                email_obj.save()

                # ============================================================
                # Redirect to Allauth confirm-email page like new users
                # Add ?annual=1 so templates can behave differently if needed
                # ============================================================
                if not request.path.startswith("/accounts/"):
                    return redirect(
                        reverse("account_email_verification_sent") + "?annual=1"
                    )

            # =====================================================================
            # STANDARD ENFORCEMENT (same as your original)
            # =====================================================================
            status = profile.verification_status

            # 1. BANNED USERS
            if status == "banned":
                logout(request)
                return redirect("/banned/")

            # 2. COMMERCIAL USERS
            if status == "commercial":
                quota = getattr(user, "variant_quota", None)

                if quota is None:
                    if not request.path.startswith("/commercial/"):
                        return redirect("/commercial/")
                    return self.get_response(request)

                quota.check_subscription_status()
                quota.reset_if_needed()

                if quota.effective_allowance > 0:
                    return self.get_response(request)

                if not request.path.startswith("/commercial/"):
                    return redirect("/commercial/")
                return self.get_response(request)

            # 3. VERIFIED / AUTO_VERIFIED USERS
            if status in ("verified", "auto_verified"):
                quota = getattr(user, "variant_quota", None)
                if quota:
                    quota.check_subscription_status()
                    quota.reset_if_needed()
                return self.get_response(request)

            # 4. NOT VERIFIED
            for allowed in self.allowed_prefixes:
                if request.path.startswith(allowed):
                    return self.get_response(request)

            return redirect("/verify/")

        # Anonymous users
        return self.get_response(request)


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