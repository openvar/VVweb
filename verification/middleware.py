# verification/middleware.py

from datetime import timedelta

from django.contrib.auth import logout
from django.shortcuts import redirect
from django.urls import reverse, resolve, Resolver404
from django.utils import timezone

from allauth.account.models import EmailAddress


class TierEnforcementMiddleware:
    """
    Entitlement + annual re-validation middleware (logout/login safe).

    • New user (terms_accepted_at is None):
        - email NOT verified -> /accounts/confirm-email/        (no ?annual=1)
        - email verified     -> /verify/

    • Existing user (auto-expired: terms_accepted_at + 365d <= now):
        - FULL RESET once (profile fields + Allauth unverified; keep terms timestamp).
        - While expired:
            - NOT verified -> /accounts/confirm-email/?annual=1
            - verified     -> /verify/
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
            "/accounts/confirm-email/",
            "/accounts/email/",
            "/accounts/resend-confirmation/",
            "/static/",
        ]

    def __call__(self, request):
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

        # Ensure Allauth row exists and one is primary
        email_row = None
        if user.email:
            email_row = EmailAddress.objects.filter(user=user, email__iexact=user.email).order_by("-primary").first()
            if not email_row:
                email_row = EmailAddress.objects.filter(user=user).order_by("-primary").first()
            if not email_row:
                email_row = EmailAddress.objects.create(user=user, email=user.email, primary=True, verified=False)
            elif not email_row.primary:
                email_row.primary = True
                email_row.save(update_fields=["primary"])

        # ANY verified row is considered confirmed
        email_verified_now = EmailAddress.objects.filter(user=user, verified=True).exists()

        # States
        now = timezone.now()
        terms = profile.terms_accepted_at
        is_new_user_terms = (terms is None)
        is_auto_expired = (terms is not None) and (now >= terms + timedelta(days=365))

        # NEW USER (no reset)
        if is_new_user_terms and not is_auto_expired:
            if user.email:
                request.session["account_email"] = user.email

            if not email_verified_now:
                if not request.path.startswith("/accounts/confirm-email/"):
                    return redirect(reverse("account_email_verification_sent"))
                return self.get_response(request)
            if not request.path.startswith("/verify/"):
                return redirect("/verify/")
            return self.get_response(request)

        # EXPIRED (idempotent reset)
        if is_auto_expired:
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

                if email_row:
                    email_row.verified = False
                    email_row.primary = True
                    email_row.save()
                    EmailAddress.objects.filter(user=user).exclude(pk=email_row.pk).update(primary=False)

                email_verified_now = False  # reflect immediately

            # Always prep the landing page context while expired
            if user.email:
                request.session["account_email"] = user.email
            request.session["annual_revalidation"] = True

            # Routing while still expired
            if not email_verified_now:
                # 1) Allow Allauth token URL to pass:
                #    - path style:  /accounts/confirm-email/<key>/
                #    - query style: /accounts/confirm-email/?key=<token>
                if request.path.startswith("/accounts/confirm-email/"):
                    # query-style token
                    if request.GET.get("key"):
                        return self.get_response(request)
                    # path-style token
                    try:
                        rm = resolve(request.path_info)
                        if rm.url_name == "account_confirm_email":
                            return self.get_response(request)
                    except Resolver404:
                        pass
                    # landing: normalize ?annual=1
                    if request.GET.get("annual") != "1":
                        return redirect(reverse("account_email_verification_sent") + "?annual=1")
                    return self.get_response(request)

                # 2) Allow resend + email management
                if request.path.startswith("/accounts/resend-confirmation/") or request.path.startswith("/accounts/email/"):
                    return self.get_response(request)

                # 3) Otherwise force the annual landing
                return redirect(reverse("account_email_verification_sent") + "?annual=1")

            # Verified -> proceed to profile verification
            if not request.path.startswith("/verify/"):
                return redirect("/verify/")
            return self.get_response(request)

        # RECENT TERMS: standard enforcement
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
            try:
                if quota.effective_allowance > 0:
                    return self.get_response(request)
            except Exception:
                pass
            if not request.path.startswith("/commercial/"):
                return redirect("/commercial/")
            return self.get_response(request)

        if status in ("verified", "auto_verified"):
            return self.get_response(request)

        # NOT VERIFIED with recent terms -> allow only whitelisted paths
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
