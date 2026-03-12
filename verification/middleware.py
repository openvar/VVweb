# verification/middleware.py (TierEnforcementMiddleware with annual re‑validation)

from datetime import timedelta

from django.contrib.auth import logout
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone


class TierEnforcementMiddleware:
    """
    Enforces VariantValidator’s mandatory verification & entitlement model.

    Rules:

      • BANNED → logout + /banned/
      • COMMERCIAL → allow only if effective_allowance > 0 (institutional or trial)
      • VERIFIED (non-commercial) → allow access, with institutional uplift if active
      • PENDING / NOT_STARTED → locked to /verify/

    Additionally:
      • ANNUAL RE-VALIDATION → if terms_accepted_at is None or >= 1 year old,
        reset verification state and redirect to /verify/.
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
            "/static/",
        ]

    def __call__(self, request):
        # Allow logout before enforcement
        if request.path.startswith("/accounts/logout"):
            return self.get_response(request)

        # Admin panel allowed
        if request.path.startswith("/admin/"):
            return self.get_response(request)

        user = request.user

        # ============================================================
        # AUTHENTICATED USERS ONLY
        # ============================================================
        if user.is_authenticated:
            # Always normalise stored email
            if user.email:
                lower = user.email.lower().strip()
                if lower != user.email:
                    user.email = lower
                    user.save(update_fields=["email"])

            profile = getattr(user, "profile", None)

            # Safety check
            if profile is None:
                logout(request)
                return redirect(reverse("account_login"))

            # ============================================================
            # ANNUAL RE‑VALIDATION (runs on every authenticated request)
            #   • If terms_accepted_at is None OR now >= terms_accepted_at + 365 days:
            #       - Reset verification-critical fields
            #       - Redirect to verification entry (/verify/)
            # ============================================================
            needs_revalidation = False
            if profile.terms_accepted_at is None:
                needs_revalidation = True
            else:
                one_year_later = profile.terms_accepted_at + timedelta(days=365)
                if timezone.now() >= one_year_later:
                    needs_revalidation = True

            if needs_revalidation:
                # Reset verification requirements
                profile.email_is_verified = False
                profile.terms_accepted_at = None
                profile.org_type = None
                profile.verification_status = "not_started"
                profile.verified_at = None
                profile.verified_by = None
                profile.rejection_reason = ""
                profile.save()

                # If not already inside verification flow, send them there
                if not request.path.startswith("/verify/"):
                    return redirect("/verify/")

            # ============================================================
            # CONTINUE NORMAL ENFORCEMENT AFTER POSSIBLE RESET
            # ============================================================
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

                # CRITICAL: recalc expiry + resets EVERY request
                quota.check_subscription_status()
                quota.reset_if_needed()

                # Allow access ONLY if allowance > 0
                if quota.effective_allowance > 0:
                    return self.get_response(request)

                # Otherwise redirect
                if not request.path.startswith("/commercial/"):
                    return redirect("/commercial/")
                return self.get_response(request)

            # 3. VERIFIED or AUTO_VERIFIED USERS
            if status in ("verified", "auto_verified"):
                quota = getattr(user, "variant_quota", None)
                if quota:
                    # CRITICAL: recalc expiry + resets EVERY request
                    quota.check_subscription_status()
                    quota.reset_if_needed()
                return self.get_response(request)

            # 4. NOT VERIFIED (pending / not_started)
            for allowed in self.allowed_prefixes:
                if request.path.startswith(allowed):
                    return self.get_response(request)

            return redirect("/verify/")

        # ============================================================
        # ANONYMOUS USERS
        # ============================================================
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
