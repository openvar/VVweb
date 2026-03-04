from django.shortcuts import redirect
from django.urls import reverse
from django.contrib.auth import logout


class TierEnforcementMiddleware:
    """
    Enforces VariantValidator’s mandatory verification & entitlement model.

    Rules:

      • BANNED → logout + /banned/
      • COMMERCIAL → allow only if effective_allowance > 0 (institutional or trial)
      • VERIFIED (non-commercial) → allow access
      • PENDING / NOT_STARTED → locked to /verify/
    """

    def __init__(self, get_response):
        self.get_response = get_response

        # Paths allowed before full verification
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

        # Allow logout to proceed before ANY enforcement
        if request.path.startswith("/accounts/logout"):
            return self.get_response(request)

        # Admin panel always allowed
        if request.path.startswith("/admin/"):
            return self.get_response(request)

        user = request.user

        # ===============================
        # Only enforce for authenticated users
        # ===============================
        if user.is_authenticated:

            # Always normalise email
            if user.email:
                lower = user.email.lower().strip()
                if lower != user.email:
                    user.email = lower
                    user.save(update_fields=["email"])

            profile = getattr(user, "profile", None)

            # Safety: missing profile → force logout
            if profile is None:
                logout(request)
                return redirect(reverse("account_login"))

            status = profile.verification_status

            # ============================================================
            # 1. BANNED USERS → immediate logout
            # ============================================================
            if status == "banned":
                logout(request)
                return redirect("/banned/")

            # ============================================================
            # 2. COMMERCIAL USERS
            # ============================================================
            if status == "commercial":

                quota = getattr(user, "variant_quota", None)

                # No quota = blocked
                if quota is None:
                    if not request.path.startswith("/commercial/"):
                        return redirect("/commercial/")
                    return self.get_response(request)

                # **CRITICAL FIX** – recalc subscription, institution expiry, monthly reset
                quota.check_subscription_status()
                quota.reset_if_needed()

                # Commercial user WITH allowance (trial or institutional)
                if quota.effective_allowance > 0:
                    return self.get_response(request)

                # Commercial user with NO allowance → must go to /commercial/
                if not request.path.startswith("/commercial/"):
                    return redirect("/commercial/")
                return self.get_response(request)

            # ============================================================
            # 3. VERIFIED or AUTO_VERIFIED USERS
            # ============================================================
            if status in ("verified", "auto_verified"):

                quota = getattr(user, "variant_quota", None)
                if quota:
                    # **CRITICAL FIX** – handle expiry and reset each request
                    quota.check_subscription_status()
                    quota.reset_if_needed()

                return self.get_response(request)

            # ============================================================
            # 4. NOT VERIFIED → HARD LOCKOUT
            # ============================================================
            for allowed in self.allowed_prefixes:
                if request.path.startswith(allowed):
                    return self.get_response(request)

            return redirect("/verify/")

        # Anonymous users unaffected
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