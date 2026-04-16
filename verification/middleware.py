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

    Annual re-validation (clean revert style):

    • New user (terms_accepted_at is None):
        - email NOT verified -> /accounts/confirm-email/
        - email verified     -> /verify/
      (No reset for new users)

    • Auto-expired (terms_accepted_at + 365d <= now):
        - FULL RESET exactly once:
            * profile.email_is_verified = False
            * profile.verification_status = "not_started"
            * profile.org_type = None
            * profile.jobrole = ""
            * profile.personal_info_is_completed = False
            * profile.completion_level = 0
            * profile.verified_at = None
            * profile.verified_by = None
            * profile.rejection_reason = ""
            * Allauth EmailAddress: set verified=False for all rows
            * IMPORTANT: set profile.terms_accepted_at = None  (becomes "new" after reset)
            * NEW: profile.reset_reason="auto", profile.reset_at=now  (differentiate from true new)
        - After reset (with terms_accepted_at=None), route as a new user.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        # Minimal allowlist to avoid loops while unverified
        self.allow_while_unverified = (
            "/accounts/confirm-email/",        # landing and token views
            "/accounts/resend-confirmation/",  # resend endpoint
            "/accounts/email/",                # email mgmt
            "/accounts/login/",
            "/accounts/logout/",
            "/accounts/signup/",
            "/verify/",                        # verification UI
            "/commercial/",
            "/logout/",
            "/static/",
        )

    def __call__(self, request):
        # Always allow admin + logout before enforcement
        if request.path.startswith("/admin/") or request.path.startswith("/accounts/logout"):
            return self.get_response(request)

        user = request.user
        if not user.is_authenticated:
            # Anonymous (e.g., clicking the token from email) → let Allauth run
            return self.get_response(request)

        # Normalize stored email
        if user.email:
            lower = user.email.lower().strip()
            if lower != user.email:
                user.email = lower
                user.save(update_fields=["email"])

        # Require profile
        profile = getattr(user, "profile", None)
        if not profile:
            logout(request)
            return redirect(reverse("account_login"))

        # Allauth verification state (any verified row counts)
        email_verified_now = EmailAddress.objects.filter(user=user, verified=True).exists()

        # Terms state
        now = timezone.now()
        terms = profile.terms_accepted_at
        is_new = (terms is None)
        is_expired = (terms is not None) and (now >= terms + timedelta(days=365))

        # -------------------------------------------------
        # AUTO-EXPIRED → one-time full reset, then behave as "new"
        # -------------------------------------------------
        if is_expired:
            # FULL PROFILE reset (leave user object intact)
            profile.email_is_verified = False
            profile.verification_status = "not_started"
            profile.org_type = None
            profile.jobrole = ""
            profile.personal_info_is_completed = False
            profile.completion_level = 0
            profile.verified_at = None
            profile.verified_by = None
            profile.rejection_reason = ""
            # IMPORTANT: blank terms so subsequent requests are treated as "new"
            profile.terms_accepted_at = None
            # NEW: mark why/when this reset happened
            profile.reset_reason = "auto"
            profile.reset_at = now
            profile.save(update_fields=[
                "email_is_verified", "verification_status", "org_type", "jobrole",
                "personal_info_is_completed", "completion_level",
                "verified_at", "verified_by", "rejection_reason",
                "terms_accepted_at", "reset_reason", "reset_at",
            ])

            # Allauth: mark all addresses as unverified
            EmailAddress.objects.filter(user=user).update(verified=False)
            email_verified_now = False  # reflect immediately

            # From next request onward, the branch below ("new") will apply.
            # Fall through to the "new" logic without further redirects here.

        # -------------------------------------------------
        # NEW (terms is None)  — includes auto-expired after reset
        # -------------------------------------------------
        if profile.terms_accepted_at is None:
            # helpful: show address on landing
            if user.email:
                request.session["account_email"] = user.email

            if not email_verified_now:
                # Allow confirm-email landing/token/resend/email mgmt to run
                for allowed in self.allow_while_unverified:
                    if request.path.startswith(allowed):
                        return self.get_response(request)
                # Otherwise send to confirm-email landing
                return redirect(reverse("account_email_verification_sent"))

            # Verified → proceed to profile verification UI
            if not request.path.startswith("/verify/"):
                return redirect("/verify/")
            return self.get_response(request)

        # -------------------------------------------------
        # RECENT TERMS (not expired): standard enforcement
        # -------------------------------------------------
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

            # If your quota model exposes these, keep them; otherwise omit.
            try:
                quota.check_subscription_status()
                quota.reset_if_needed()
            except Exception:
                pass

            try:
                if getattr(quota, "effective_allowance", 0) > 0:
                    return self.get_response(request)
            except Exception:
                pass

            if not request.path.startswith("/commercial/"):
                return redirect("/commercial/")
            return self.get_response(request)

        if status in ("verified", "auto_verified"):
            return self.get_response(request)

        # Not verified with recent terms → allow only the whitelist
        for allowed in self.allow_while_unverified:
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
