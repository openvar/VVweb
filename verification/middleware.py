# verification/middleware.py

from datetime import timedelta
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone
from allauth.account.models import EmailAddress


class TierEnforcementMiddleware:

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

        user = request.user

        if not user.is_authenticated:
            return self.get_response(request)

        # normalize email
        if user.email:
            lowered = user.email.lower().strip()
            if lowered != user.email:
                user.email = lowered
                user.save(update_fields=["email"])

        profile = getattr(user, "profile", None)
        if profile is None:
            logout(request)
            return redirect(reverse("account_login"))

        # ensure Allauth EmailAddress exists
        email_obj, _ = EmailAddress.objects.get_or_create(
            user=user,
            email=user.email,
            defaults={"primary": True, "verified": False},
        )
        email_verified_now = email_obj.verified

        # ---------------------------------------------------------------------
        # DETERMINE STATE
        # ---------------------------------------------------------------------
        now = timezone.now()
        terms = profile.terms_accepted_at
        new_user = (terms is None)
        expired = (terms is not None) and (now >= terms + timedelta(days=365))

        # ---------------------------------------------------------------------
        # NEW USER FLOW (NEVER RESET)
        # ---------------------------------------------------------------------
        if new_user and not expired:
            request.session["account_email"] = user.email

            if not email_verified_now:
                if not request.path.startswith("/accounts/confirm-email/"):
                    return redirect(reverse("account_email_verification_sent"))
                return self.get_response(request)

            if not request.path.startswith("/verify/"):
                return redirect("/verify/")
            return self.get_response(request)

        # ---------------------------------------------------------------------
        # ANNUAL EXPIRED FLOW
        # ONE-TIME FULL RESET ONLY
        # ---------------------------------------------------------------------
        if expired:

            reset_done = request.session.get("annual_reset_done", False)

            if not reset_done:
                # FULL RESET exactly once
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

                # Allauth: unify this one verified flag
                email_obj.verified = False
                email_obj.primary = True
                email_obj.save()

                # mark reset done
                request.session["annual_reset_done"] = True

                # after reset, email is unverified
                email_verified_now = False

            # always expose email for template
            request.session["account_email"] = user.email
            request.session["annual_revalidation"] = True

            # ROUTING UNDER EXPIRED TERMS
            if not email_verified_now:
                if request.path.startswith("/accounts/confirm-email/"):
                    if request.GET.get("annual") != "1":
                        return redirect(reverse("account_email_verification_sent") + "?annual=1")
                    return self.get_response(request)

                return redirect(reverse("account_email_verification_sent") + "?annual=1")

            # email verified → user verification page
            if not request.path.startswith("/verify/"):
                return redirect("/verify/")
            return self.get_response(request)

        # ---------------------------------------------------------------------
        # RECENT TERMS
        # ---------------------------------------------------------------------
        status = profile.verification_status

        if status == "banned":
            logout(request)
            return redirect("/banned/")

        if status == "commercial":
            return self.get_response(request)

        if status in ("verified", "auto_verified"):
            return self.get_response(request)

        # not verified but not expired
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