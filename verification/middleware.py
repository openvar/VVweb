# verification/middleware.py

from datetime import timedelta

from django.contrib.auth import logout
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone

from allauth.account.models import EmailAddress


class TierEnforcementMiddleware:
    """
    Enforces VariantValidator’s identity, verification, and entitlement rules.

    Annual re‑validation (EXACT new‑account behaviour, state‑driven):
      • If terms_accepted_at is None OR >= 1 year old:
          - Keep/repair Allauth EmailAddress but DO NOT force-undo a verified email.
          - Reset profile to a pre‑verification state (idempotent).
          - Route based on email verification:
              - email NOT verified  -> /accounts/confirm-email/ (account_email_verification_sent)
              - email IS verified   -> /verify/
    """

    def __init__(self, get_response):
        self.get_response = get_response

        # Paths allowed during verification lockout
        self.allowed_prefixes = [
            "/verify/",
            "/commercial/",
            "/logout/",
            "/accounts/login/",
            "/accounts/logout/",
            "/accounts/signup/",
            "/accounts/confirm-email/",       # allauth confirmation pages
            "/accounts/email/",               # allauth email management
            "/accounts/resend-confirmation/", # your resend endpoint
            "/static/",
        ]

    def __call__(self, request):

        # Allow logout/admin before enforcement
        if request.path.startswith("/accounts/logout") or request.path.startswith("/admin/"):
            return self.get_response(request)

        user = request.user

        if user.is_authenticated:
            # Normalize stored email
            if user.email:
                lowered = user.email.lower().strip()
                if lowered != user.email:
                    user.email = lowered
                    user.save(update_fields=["email"])

            profile = getattr(user, "profile", None)
            if profile is None:
                logout(request)
                return redirect(reverse("account_login"))

            # ------------------------------------------------------------
            # Determine if annual re‑validation is required
            # ------------------------------------------------------------
            now = timezone.now()
            needs_revalidation = False
            if profile.terms_accepted_at is None:
                needs_revalidation = True
            else:
                if now >= profile.terms_accepted_at + timedelta(days=365):
                    needs_revalidation = True

            # Resolve Allauth email state (create row if missing, do NOT force unverify)
            email_verified_now = False
            if user.email:
                email_obj, created = EmailAddress.objects.get_or_create(
                    user=user,
                    email=user.email,
                    defaults={"primary": True, "verified": False},
                )
                # Always keep a single primary
                if not email_obj.primary:
                    email_obj.primary = True
                    email_obj.save(update_fields=["primary"])
                email_verified_now = bool(email_obj.verified)

            # ------------------------------------------------------------
            # If re‑validation required, reset profile idempotently,
            # then route based on email verification state
            # ------------------------------------------------------------
            if needs_revalidation:
                # Reset profile to pre‑verification state (does not touch EmailAddress.verified)
                # Safe to run repeatedly: values are idempotent.
                profile.org_type = None
                profile.jobrole = ""
                profile.personal_info_is_completed = False
                profile.completion_level = 0
                profile.verification_status = "not_started"
                profile.verified_at = None
                profile.verified_by = None
                profile.rejection_reason = ""
                # Keep profile.email_is_verified in sync with Allauth view of the world
                profile.email_is_verified = bool(email_verified_now)
                # Do not set terms_accepted_at here; it remains None until user accepts again
                profile.save()

                # Route according to email verification:
                # A/D) terms missing or expired AND email NOT verified  -> confirm-email page
                if not email_verified_now:
                    if not request.path.startswith("/accounts/"):
                        return redirect(
                            reverse("account_email_verification_sent") + "?annual=1"
                        )
                    # Already on /accounts/... -> allow through
                    return self.get_response(request)

                # B/C) terms missing or expired AND email IS verified -> /verify/ (terms/role/org)
                if not request.path.startswith("/verify/"):
                    return redirect("/verify/")
                return self.get_response(request)

            # ------------------------------------------------------------
            # Post‑revalidation: standard entitlement enforcement
            # ------------------------------------------------------------
            status = profile.verification_status

            # 1) BANNED
            if status == "banned":
                logout(request)
                return redirect("/banned/")

            # 2) COMMERCIAL
            if status == "commercial":
                quota = getattr(user, "variant_quota", None)

                if quota is None:
                    if not request.path.startswith("/commercial/"):
                        return redirect("/commercial/")
                    return self.get_response(request)

                # Recalc expiry + resets EVERY request
                quota.check_subscription_status()
                quota.reset_if_needed()

                if quota.effective_allowance > 0:
                    return self.get_response(request)

                if not request.path.startswith("/commercial/"):
                    return redirect("/commercial/")
                return self.get_response(request)

            # 3) VERIFIED / AUTO_VERIFIED (non‑commercial)
            if status in ("verified", "auto_verified"):
                quota = getattr(user, "variant_quota", None)
                if quota:
                    quota.check_subscription_status()
                    quota.reset_if_needed()
                return self.get_response(request)

            # 4) NOT VERIFIED -> only allow whitelisted paths
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