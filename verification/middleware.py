from datetime import timedelta

from django.contrib.auth import logout
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone

from allauth.account.models import EmailAddress


class TierEnforcementMiddleware:
    """
    VariantValidator entitlement + annual re-validation middleware.

    SIMPLE RULES:
    ----------------------------------------------
    If (terms_accepted_at is None) OR (>1 year old):
        → FULL RESET (profile + Allauth email)
        → Redirect to /accounts/confirm-email/?annual=1
        BUT allow that page to render when already on it.
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
            "/accounts/email/",
            "/accounts/resend-confirmation/",
            "/accounts/confirm-email/",   # must not redirect away from this
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
            if not profile:
                logout(request)
                return redirect(reverse("account_login"))

            # -----------------------------------------------------
            # Determine if annual reset is required
            # -----------------------------------------------------
            now = timezone.now()

            needs_revalidation = False
            if profile.terms_accepted_at is None:
                needs_revalidation = True
            else:
                if now >= profile.terms_accepted_at + timedelta(days=365):
                    needs_revalidation = True

            # -----------------------------------------------------
            # FULL RESET (identical to admin action)
            # -----------------------------------------------------
            if needs_revalidation:

                # Reset profile to pre-verification state
                profile.email_is_verified = False
                profile.terms_accepted_at = None
                profile.verification_status = "not_started"
                profile.org_type = None
                profile.jobrole = ""
                profile.personal_info_is_completed = False
                profile.completion_level = 0
                profile.verified_at = None
                profile.verified_by = None
                profile.rejection_reason = ""
                profile.save()

                # Reset Allauth email object
                if user.email:
                    email_obj, _ = EmailAddress.objects.get_or_create(
                        user=user,
                        email=user.email.lower().strip(),
                        defaults={"primary": True, "verified": False},
                    )

                    email_obj.verified = False
                    email_obj.primary = True
                    email_obj.save()

                    EmailAddress.objects.filter(user=user).exclude(pk=email_obj.pk).update(primary=False)

                # -------------------------------------------------
                # Redirect to confirm-email ONLY if not already there
                # -------------------------------------------------
                if not request.path.startswith("/accounts/confirm-email/"):
                    return redirect(reverse("account_email_verification_sent") + "?annual=1")

                # If already on the confirm page — allow rendering
                return self.get_response(request)

            # -----------------------------------------------------
            # STANDARD ENFORCEMENT (unchanged)
            # -----------------------------------------------------
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

            # NOT VERIFIED → only allow allowed paths
            for allowed in self.allowed_prefixes:
                if request.path.startswith(allowed):
                    return self.get_response(request)

            return redirect("/verify/")

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