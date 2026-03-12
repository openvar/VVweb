# verification/middleware.py

from datetime import timedelta

from django.contrib.auth import logout
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone

from allauth.account.models import EmailAddress


class TierEnforcementMiddleware:
    """
    Entitlement + annual re-validation middleware (logout/login safe).

    • New user (terms_accepted_at is None):
        - email NOT verified -> /accounts/confirm-email/        (no ?annual=1)
        - email verified     -> /verify/
      (No reset for new users)

    • Existing user (auto-expired: terms_accepted_at + 365d <= now):
        - Perform FULL RESET the first time we detect expiry:
            * profile.email_is_verified = False
            * profile.verification_status = "not_started"
            * profile.org_type = None
            * profile.jobrole = ""
            * profile.personal_info_is_completed = False
            * profile.completion_level = 0
            * profile.verified_at = None
            * profile.verified_by = None
            * profile.rejection_reason = ""
            * Allauth EmailAddress: ensure exists, primary=True, verified=False
          IMPORTANT: we DO NOT set terms_accepted_at = None for auto-expiry.
                     We leave the old timestamp so the system can still
                     recognize “annual mode” after logout/login.
        - On every request while terms > 1 year:
            * If email NOT verified -> /accounts/confirm-email/?annual=1
            * If email verified     -> /verify/
      (Reset is idempotent: performed only if not already in pre-verification state)
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
            "/accounts/confirm-email/",       # Allauth confirm-email landing & key URLs
            "/accounts/email/",               # Allauth email management
            "/accounts/resend-confirmation/", # custom resend endpoint
            "/static/",
        ]

    def __call__(self, request):
        # Allow logout/admin before enforcement
        if request.path.startswith("/accounts/logout") or request.path.startswith("/admin/"):
            return self.get_response(request)

        user = getattr(request, "user", None)
        if not (user and user.is_authenticated):
            return self.get_response(request)

        # Normalize stored email
        if user.email:
            lowered = user.email.lower().strip()
            if lowered != user.email:
                user.email = lowered
                user.save(update_fields=["email"])

        profile = getattr(user, "profile", None)
        if not profile:
            logout(request)
            return redirect(reverse("account_login"))

        # Resolve Allauth email entry (create if missing); do not auto-send here
        email_verified_now = False
        email_obj = None
        if user.email:
            email_obj, _ = EmailAddress.objects.get_or_create(
                user=user,
                email=user.email,
                defaults={"primary": True, "verified": False},
            )
            if not email_obj.primary:
                email_obj.primary = True
                email_obj.save(update_fields=["primary"])
            email_verified_now = bool(email_obj.verified)

        # ---- Determine states ----
        now = timezone.now()
        terms = profile.terms_accepted_at
        is_new_user_terms = (terms is None)
        is_auto_expired = (terms is not None) and (now >= terms + timedelta(days=365))

        # ---- NEW USER (no reset) ----
        if is_new_user_terms and not is_auto_expired:
            # Keep a helpful email in session for the template
            if user.email:
                request.session["account_email"] = user.email

            if not email_verified_now:
                if not request.path.startswith("/accounts/confirm-email/"):
                    return redirect(reverse("account_email_verification_sent"))
                return self.get_response(request)
            else:
                if not request.path.startswith("/verify/"):
                    return redirect("/verify/")
                return self.get_response(request)

        # ---- AUTO-EXPIRED (idempotent FULL RESET, but keep terms timestamp) ----
        if is_auto_expired:
            # Perform the full reset only if the profile is NOT already in pre-verification state
            profile_needs_reset = (
                profile.verification_status != "not_started" or
                profile.org_type is not None or
                profile.jobrole != "" or
                profile.personal_info_is_completed or
                profile.completion_level != 0 or
                profile.verified_at is not None or
                profile.verified_by is not None or
                profile.rejection_reason != "" or
                profile.email_is_verified  # any True here means it's not fully reset
            )

            if profile_needs_reset:
                # FULL PROFILE reset (leave terms_accepted_at unchanged)
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

                # ALLAUTH: ensure exists, primary, and unverified
                if email_obj:
                    email_obj.verified = False
                    email_obj.primary = True
                    email_obj.save()
                    EmailAddress.objects.filter(user=user).exclude(pk=email_obj.pk).update(primary=False)

                    # IMPORTANT: reflect the unverified state immediately for routing below
                    email_verified_now = False

                # Make the email address visible on landing (even after logout)
                if user.email:
                    request.session["account_email"] = user.email

                # Mark this browser session as being in annual mode so the template can show annual copy
                request.session["annual_revalidation"] = True

            # Route while terms still > 1 year:
            if not email_verified_now:
                # Always show annual landing (logout/login safe)
                if not request.path.startswith("/accounts/confirm-email/"):
                    return redirect(reverse("account_email_verification_sent") + "?annual=1")
                return self.get_response(request)
            else:
                # Email verified; proceed to profile verification (/verify/)
                if not request.path.startswith("/verify/"):
                    return redirect("/verify/")
                return self.get_response(request)

        # ---- Recent terms: standard enforcement ----
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

            if quota.effective_allowance > 0:
                return self.get_response(request)

            if not request.path.startswith("/commercial/"):
                return redirect("/commercial/")
            return self.get_response(request)

        if status in ("verified", "auto_verified"):
            quota = getattr(user, "variant_quota", None)
            if quota:
                quota.check_subscription_status()
                quota.reset_if_needed()
            return self.get_response(request)

        # Pending/not_started with recent terms → allow only whitelisted paths
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