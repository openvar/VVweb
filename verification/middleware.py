from datetime import timedelta

from django.contrib.auth import logout
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone

from allauth.account.models import EmailAddress


class TierEnforcementMiddleware:
    """
    VariantValidator entitlement + annual re-validation middleware.

    FINAL RULES
    -----------
    • New user (terms_accepted_at is None):
        - email NOT verified -> /accounts/confirm-email/
        - email verified     -> /verify/
      (No profile/email reset for new users)

    • Existing user with terms expired (terms_accepted_at + 365d <= now):
        - Perform FULL RESET once per browser session:
            * profile.email_is_verified = False
            * profile.terms_accepted_at = None
            * profile.verification_status = "not_started"
            * profile.org_type = None
            * profile.jobrole = ""
            * profile.personal_info_is_completed = False
            * profile.completion_level = 0
            * profile.verified_at = None
            * profile.verified_by = None
            * profile.rejection_reason = ""
            * Allauth EmailAddress: ensure exists, primary=True, verified=False
        - Redirect to /accounts/confirm-email/?annual=1
        - After user confirms email (verified=True, terms still None) -> /verify/

    • Loop protection: only perform the FULL RESET once per browser session
      when auto-expiry is first detected (session key: 'annual_full_reset_done').

    • Normal entitlement enforcement (banned, commercial, verified) remains unchanged.
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
            "/accounts/confirm-email/",       # Allauth confirm-email landing & key URLs
            "/accounts/email/",               # Allauth email management
            "/accounts/resend-confirmation/", # Your custom resend endpoint
            "/static/",
        ]

    def __call__(self, request):
        # Allow logout/admin before enforcement
        if request.path.startswith("/accounts/logout") or request.path.startswith("/admin/"):
            return self.get_response(request)

        user = getattr(request, "user", None)
        if not (user and user.is_authenticated):
            return self.get_response(request)

        # Normalize stored user.email
        if user.email:
            lowered = user.email.lower().strip()
            if lowered != user.email:
                user.email = lowered
                user.save(update_fields=["email"])

        profile = getattr(user, "profile", None)
        if not profile:
            logout(request)
            return redirect(reverse("account_login"))

        # ---------- Determine current state ----------
        now = timezone.now()
        terms = profile.terms_accepted_at
        is_new_terms_state = terms is None
        is_auto_expired = (terms is not None) and (now >= terms + timedelta(days=365))

        # Resolve Allauth email entry (create if missing) without forcing its verified state here.
        email_verified_now = False
        if user.email:
            email_obj, _ = EmailAddress.objects.get_or_create(
                user=user,
                email=user.email,
                defaults={"primary": True, "verified": False},
            )
            # Ensure exactly one primary for safety
            if not email_obj.primary:
                email_obj.primary = True
                email_obj.save(update_fields=["primary"])
            email_verified_now = bool(email_obj.verified)

        # ---------- AUTO-EXPIRED: FULL RESET (once per browser session) ----------
        reset_done = request.session.get("annual_full_reset_done", False)
        if is_auto_expired and not reset_done:
            # PROFILE full reset (identical to admin)
            profile.email_is_verified = False
            profile.terms_accepted_at = None        # collapse to None after reset
            profile.verification_status = "not_started"
            profile.org_type = None
            profile.jobrole = ""
            profile.personal_info_is_completed = False
            profile.completion_level = 0
            profile.verified_at = None
            profile.verified_by = None
            profile.rejection_reason = ""
            profile.save()

            # ALLAUTH full reset (unverify email and ensure primary)
            if user.email:
                email_obj, _ = EmailAddress.objects.get_or_create(
                    user=user,
                    email=user.email,
                    defaults={"primary": True, "verified": False},
                )
                email_obj.verified = False
                email_obj.primary = True
                email_obj.save()
                # Demote any others
                EmailAddress.objects.filter(user=user).exclude(pk=email_obj.pk).update(primary=False)

            # One-time guard for this browser session
            request.session["annual_full_reset_done"] = True

            # Redirect to confirm-email (annual mode) unless already there
            if not request.path.startswith("/accounts/confirm-email/"):
                return redirect(reverse("account_email_verification_sent") + "?annual=1")
            return self.get_response(request)

        # ---------- TERMS IS NONE (new user OR post-reset) ----------
        if is_new_terms_state:
            if not email_verified_now:
                # New user or recently reset-but-not-yet-confirmed -> confirm email
                if not request.path.startswith("/accounts/confirm-email/"):
                    # Add '?annual=1' only if we performed an auto reset this session
                    suffix = "?annual=1" if request.session.get("annual_full_reset_done") else ""
                    return redirect(reverse("account_email_verification_sent") + suffix)
                return self.get_response(request)
            else:
                # Email verified, but terms/org/role not completed -> /verify/
                if not request.path.startswith("/verify/"):
                    return redirect("/verify/")
                return self.get_response(request)

        # ---------- If we reach here, terms are valid and recent. Standard enforcement ----------
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

        # 4) NOT VERIFIED (pending/not_started) with recent terms -> allow only whitelisted paths
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