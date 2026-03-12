from datetime import timedelta

from django.contrib.auth import logout
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone

from allauth.account.models import EmailAddress


class TierEnforcementMiddleware:
    """
    Enforces VariantValidator’s identity, verification and entitlement rules.

    Annual re‑validation (EXACT 'new account' behaviour):
      • On/after the 1‑year mark (or if terms never accepted):
          - Reset profile to a pre‑verification state.
          - Require email confirmation again (Allauth).
          - Then require terms/org/role via /verify/.

    Session flag 'annual_reverify_required':
      • Set to True the first time a user hits any page after annual expiry.
      • While True:
          - If email NOT verified => redirect to /accounts/confirm-email/
          - If email verified    => clear flag and redirect to /verify/
      • Prevents flipping verified status back to False after the user confirms.
    """

    def __init__(self, get_response):
        self.get_response = get_response

        # Paths allowed during verification lockout (avoid redirect loops)
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

        # Allow logout/admin early
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
            # 1) Determine if annual re‑validation is required
            # ------------------------------------------------------------
            needs_reset = False
            if profile.terms_accepted_at is None:
                needs_reset = True
            else:
                one_year_later = profile.terms_accepted_at + timedelta(days=365)
                if timezone.now() >= one_year_later:
                    needs_reset = True

            # Resolve Allauth email record (may be missing)
            email_obj = None
            email_verified_now = False
            if user.email:
                email_obj = EmailAddress.objects.filter(user=user, email=user.email).first()
                email_verified_now = bool(email_obj and email_obj.verified)

            # Session flag controlling the 2‑phase flow (email → verify)
            flag = request.session.get("annual_reverify_required", None)

            # ------------------------------------------------------------
            # 2) First entry after annual expiry: perform the reset ONCE
            #    and set session flag to drive the 2‑phase flow.
            # ------------------------------------------------------------
            if needs_reset and flag is None:
                # Reset to 'brand new' profile state (idempotent on first pass)
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

                # Ensure an Allauth EmailAddress row exists for this user/email
                if user.email:
                    email_obj, _ = EmailAddress.objects.get_or_create(
                        user=user,
                        email=user.email,
                        defaults={"primary": True, "verified": False},
                    )
                    # Force unverified exactly once at reset time
                    email_obj.primary = True
                    email_obj.verified = False
                    email_obj.save()

                # Arm the session flag so subsequent requests are guided
                request.session["annual_reverify_required"] = True
                flag = True
                email_verified_now = False  # we've just forced unverified

            # ------------------------------------------------------------
            # 3) While the flag is set:
            #    (a) If email not yet verified => go to email confirmation page
            #    (b) If email verified => clear flag and progress to /verify/
            # ------------------------------------------------------------
            if flag is True:
                # Recompute current verification (user may have just clicked the link)
                if user.email:
                    email_obj = EmailAddress.objects.filter(user=user, email=user.email).first()
                    email_verified_now = bool(email_obj and email_obj.verified)

                if not email_verified_now:
                    # Keep the user at the Allauth 'email sent' screen unless already there
                    if not request.path.startswith("/accounts/"):
                        return redirect(
                            reverse("account_email_verification_sent") + "?annual=1"
                        )
                    # Already on /accounts/... -> allow through to render/email resend
                    return self.get_response(request)
                else:
                    # Email confirmed — clear flag and move into /verify/ flow
                    request.session["annual_reverify_required"] = False
                    if not request.path.startswith("/verify/"):
                        return redirect("/verify/")
                    return self.get_response(request)

            # ------------------------------------------------------------
            # 4) Post‑reset normal entitlement enforcement (unchanged)
            # ------------------------------------------------------------
            status = profile.verification_status

            # BANNED
            if status == "banned":
                logout(request)
                return redirect("/banned/")

            # COMMERCIAL
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

            # VERIFIED / AUTO_VERIFIED
            if status in ("verified", "auto_verified"):
                quota = getattr(user, "variant_quota", None)
                if quota:
                    quota.check_subscription_status()
                    quota.reset_if_needed()
                return self.get_response(request)

            # NOT VERIFIED — allow only whitelisted paths
            for allowed in self.allowed_prefixes:
                if request.path.startswith(allowed):
                    return self.get_response(request)

            return redirect("/verify/")

        # Anonymous
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