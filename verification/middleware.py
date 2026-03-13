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

    • New user  (terms_accepted_at is None):
        - email NOT verified -> /accounts/confirm-email/        (no ?annual)
        - email verified     -> /verify/
      (No reset for new users)

    • Expired   (terms_accepted_at + 365d <= now):
        - One-time FULL RESET to pre-verification state
          (DO NOT blank terms_accepted_at; keep it, so we can tell “expired” from “new”.)
        - While expired:
            - email NOT verified -> /accounts/confirm-email/
            - email verified     -> /verify/
    """

    def __init__(self, get_response):
        self.get_response = get_response

        # Whitelisted paths allowed while not fully verified/re-verified
        self.allowed_prefixes = [
            "/verify/",
            "/commercial/",
            "/logout/",
            "/accounts/login/",
            "/accounts/logout/",
            "/accounts/signup/",
            "/accounts/confirm-email/",        # landing and token paths
            "/accounts/resend-confirmation/",  # resend endpoint
            "/accounts/email/",                # email mgmt
            "/static/",
        ]

    def __call__(self, request):
        # Always allow logout/admin
        if request.path.startswith("/accounts/logout") or request.path.startswith("/admin/"):
            return self.get_response(request)

        user = request.user
        if not user.is_authenticated:
            # Anonymous (e.g., token click) → let Allauth views run unimpeded
            return self.get_response(request)

        # Normalize stored email
        if user.email:
            lower = user.email.lower().strip()
            if user.email != lower:
                user.email = lower
                user.save(update_fields=["email"])

        # Require profile
        profile = getattr(user, "profile", None)
        if not profile:
            logout(request)
            return redirect(reverse("account_login"))

        # Allauth email verification state (any verified row counts)
        email_verified_now = EmailAddress.objects.filter(user=user, verified=True).exists()

        # Terms state
        now = timezone.now()
        terms = profile.terms_accepted_at
        is_new_user = (terms is None)
        is_expired = (terms is not None) and (now >= terms + timedelta(days=365))

        # -----------------------------
        # NEW USER (no reset)
        # -----------------------------
        if is_new_user and not is_expired:
            # helpful: show address on the landing page
            if user.email:
                request.session["account_email"] = user.email

            if not email_verified_now:
                if not request.path.startswith("/accounts/confirm-email/"):
                    return redirect(reverse("account_email_verification_sent"))
                return self.get_response(request)

            if not request.path.startswith("/verify/"):
                return redirect("/verify/")
            return self.get_response(request)

        # -----------------------------
        # EXPIRED (idempotent reset)
        # -----------------------------
        if is_expired:
            # Perform the full reset only if not already in pre-verification state.
            needs_full_reset = (
                profile.email_is_verified
                or profile.verification_status != "not_started"
                or profile.org_type is not None
                or profile.jobrole != ""
                or profile.personal_info_is_completed
                or profile.completion_level != 0
                or profile.verified_at is not None
                or profile.verified_by is not None
                or profile.rejection_reason != ""
            )

            if needs_full_reset:
                # FULL PROFILE reset (but KEEP terms_accepted_at unchanged)
                profile.email_is_verified = False
                profile.verification_status = "not_started"
                profile.org_type = None
                profile.jobrole = ""
                profile.personal_info_is_completed = False
                profile.completion_level = 0
                profile.verified_at = None
                profile.verified_by = None
                profile.rejection_reason = ""
                profile.save()

                # Allauth: mark all as unverified for this user
                EmailAddress.objects.filter(user=user).update(verified=False)

                # And reflect the unverified state for routing below
                email_verified_now = False

            # helpful: show address on the landing page
            if user.email:
                request.session["account_email"] = user.email

            # Route while expired
            if not email_verified_now:
                # Allow confirm-email landing/token/resend/email mgmt to pass
                for allowed in ("/accounts/confirm-email/", "/accounts/resend-confirmation/", "/accounts/email/"):
                    if request.path.startswith(allowed):
                        return self.get_response(request)
                # Otherwise, send to the confirm landing
                return redirect(reverse("account_email_verification_sent"))

            # Email verified → proceed to profile verification
            if not request.path.startswith("/verify/"):
                return redirect("/verify/")
            return self.get_response(request)

        # -----------------------------
        # RECENT TERMS: standard enforcement
        # -----------------------------
        status = profile.verification_status

        if status == "banned":
            logout(request)
            return redirect("/banned/")

        if status == "commercial":
            quota = getattr(user, "variant_quota", None)
            if quota is None:
                if not request.path.startswith("/commercial/"):
                    return redirect("/commercial/")
                return self.get_response(request)

            quota.check_subscription_status()
            quota.reset_if_needed()

            if getattr(quota, "effective_allowance", 0) > 0:
                return self.get_response(request)

            if not request.path.startswith("/commercial/"):
                return redirect("/commercial/")
            return self.get_response(request)

        if status in ("verified", "auto_verified"):
            return self.get_response(request)

        # Not verified with recent terms → allow only whitelisted paths
        for allowed in self.allowed_prefixes:
            if request.path.startswith(allowed):
                return self.get_response(request)

        return redirect("/verify/")

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