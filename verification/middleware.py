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

        # Paths allowed during verification to avoid redirect loops
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

        # ---- Resolve Allauth email state (robust) ----
        # Ensure at least one row exists; ensure one primary; then determine
        # 'email_verified_now' by checking ANY verified row for this user.
        email_row = None
        if user.email:
            email_row = EmailAddress.objects.filter(
                user=user, email__iexact=user.email
            ).order_by("-primary").first()
            if not email_row:
                email_row = EmailAddress.objects.filter(user=user).order_by("-primary").first()
            if not email_row:
                email_row = EmailAddress.objects.create(
                    user=user, email=user.email, primary=True, verified=False
                )
            elif not email_row.primary:
                email_row.primary = True
                email_row.save(update_fields=["primary"])

        email_verified_now = EmailAddress.objects.filter(user=user, verified=True).exists()

        # ---- Determine states ----
        now = timezone.now()
        terms = profile.terms_accepted_at
        is_new_user_terms = (terms is None)
        is_auto_expired = (terms is not None) and (now >= terms + timedelta(days=365))

        # -----------------------------
        # NEW USER (no reset)
        # -----------------------------
        if is_new_user_terms and not is_auto_expired:
            # Expose email for template (resend button)
            if user.email:
                request.session["account_email"] = user.email

            if not email_verified_now:
                # Standard confirm page (no annual flag)
                if not request.path.startswith("/accounts/confirm-email/"):
                    return redirect(reverse("account_email_verification_sent"))
                return self.get_response(request)
            else:
                if not request.path.startswith("/verify/"):
                    return redirect("/verify/")
                return self.get_response(request)

        # -----------------------------
        # ANNUAL EXPIRED (idempotent FULL RESET, keep terms timestamp)
        # -----------------------------
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
                if email_row:
                    email_row.verified = False
                    email_row.primary = True
                    email_row.save()
                    EmailAddress.objects.filter(user=user).exclude(pk=email_row.pk).update(primary=False)

                # reflect unverified immediately for routing below
                email_verified_now = False

            # <<< ALWAYS set session context while expired (even if reset already happened) >>>
            if user.email:
                request.session["account_email"] = user.email
            request.session["annual_revalidation"] = True

            # ROUTE while terms still > 1 year
            if not email_verified_now:
                # Ensure we ALWAYS have ?annual=1 on the confirm page
                if request.path.startswith("/accounts/confirm-email/"):
                    if request.GET.get("annual") != "1":
                        return redirect(reverse("account_email_verification_sent") + "?annual=1")
                    return self.get_response(request)
                # Not already on confirm page -> send to annual confirm URL
                return redirect(reverse("account_email_verification_sent") + "?annual=1")

            # Email verified; continue to user verification (/verify/)
            if not request.path.startswith("/verify/"):
                return redirect("/verify/")
            return self.get_response(request)

        # -----------------------------
        # RECENT TERMS: standard enforcement
        # -----------------------------
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

            # If you recalc quota per request, call here:
            # quota.check_subscription_status()
            # quota.reset_if_needed()

            try:
                if quota.effective_allowance > 0:
                    return self.get_response(request)
            except Exception:
                pass

            if not request.path.startswith("/commercial/"):
                return redirect("/commercial/")
            return self.get_response(request)

        # 3) VERIFIED / AUTO_VERIFIED (non-commercial)
        if status in ("verified", "auto_verified"):
            # If you recalc quota per request, call here:
            # quota = getattr(user, "variant_quota", None)
            # if quota:
            #     quota.check_subscription_status()
            #     quota.reset_if_needed()
            return self.get_response(request)

        # 4) NOT VERIFIED with recent terms -> allow only whitelisted paths
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