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

    NEW USER (terms_accepted_at is None):
        - email NOT verified -> /accounts/confirm-email/              (no ?annual=1)
        - email verified     -> /verify/
      (No reset for new users)

    EXISTING USER (auto-expired: terms_accepted_at + 365d <= now):
        - Perform FULL RESET once (idempotent) to pre-verification:
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
          IMPORTANT: do NOT set terms_accepted_at = None for auto-expiry
                     (keeps expiry detectable after logout/login).

        - While terms remain > 1 year:
            * If email NOT verified -> /accounts/confirm-email/?annual=1
            * If email verified     -> /verify/
    """

    def __init__(self, get_response):
        self.get_response = get_response

        # Allowed during verification to avoid redirect loops
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

        # Ensure Allauth email row exists; do not auto-send here
        email_obj = None
        email_verified_now = False
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

        # Determine state
        now = timezone.now()
        terms = profile.terms_accepted_at
        is_new_user_terms = (terms is None)
        is_auto_expired = (terms is not None) and (now >= terms + timedelta(days=365))

        # -----------------------------
        # NEW USER (no reset)
        # -----------------------------
        if is_new_user_terms and not is_auto_expired:
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
        # ANNUAL EXPIRED (idempotent reset)
        # -----------------------------
        if is_auto_expired:
            # One-time FULL RESET (only if not already in pre-verification state)
            profile_needs_reset = (
                profile.verification_status != "not_started"
                or profile.org_type is not None
                or profile.jobrole != ""
                or profile.personal_info_is_completed
                or profile.completion_level != 0
                or profile.verified_at is not None
                or profile.verified_by is not None
                or profile.rejection_reason != ""
                or profile.email_is_verified
            )

            if profile_needs_reset:
                # PROFILE reset (keep terms_accepted_at unchanged)
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

                # ALLAUTH email: unverify & ensure primary
                if email_obj:
                    email_obj.verified = False
                    email_obj.primary = True
                    email_obj.save()
                    EmailAddress.objects.filter(user=user).exclude(pk=email_obj.pk).update(primary=False)
                    email_verified_now = False  # reflect immediately

            # Always support template with session context
            if user.email:
                request.session["account_email"] = user.email
            request.session["annual_revalidation"] = True

            # ROUTE WHILE EXPIRED
            if not email_verified_now:
                # Ensure we ALWAYS have ?annual=1 on the confirm page
                if request.path.startswith("/accounts/confirm-email/"):
                    if request.GET.get("annual") != "1":
                        # Preserve any existing query params and add annual=1
                        qs = request.GET.copy()
                        qs["annual"] = "1"
                        return redirect(f"{request.path}?{qs.urlencode()}")
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

            quota.check_subscription_status()
            quota.reset_if_needed()

            if quota.effective_allowance > 0:
                return self.get_response(request)

            if not request.path.startswith("/commercial/"):
                return redirect("/commercial/")
            return self.get_response(request)

        # 3) VERIFIED / AUTO_VERIFIED (non-commercial)
        if status in ("verified", "auto_verified"):
            quota = getattr(user, "variant_quota", None)
            if quota:
                quota.check_subscription_status()
                quota.reset_if_needed()
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
