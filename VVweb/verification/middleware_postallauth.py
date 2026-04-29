# verification/middleware_postallauth.py

from django.shortcuts import redirect
from django.urls import reverse

class PostAllauthLoginRedirectFix:
    """
    Intercept Allauth's redirect to /accounts/login/ that occurs AFTER login
    (i.e., when the user is authenticated but Allauth tries to bounce them back
    to the login form due to email not being verified yet).

    Anonymous users MUST NOT be intercepted — Allauth intentionally redirects
    anonymous users during the mandatory-email-verification workflow.

    This middleware safely overrides the unwanted redirect AFTER login,
    sending the user to /accounts/confirm-email/ instead.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Only handle redirect responses
        if not hasattr(response, "url"):
            return response

        url = response.url or ""

        # Only intercept when the USER *IS AUTHENTICATED*
        # (Anonymous bounce is part of Allauth's flow and must not be intercepted)
        if request.user.is_authenticated:

            # Allauth uses both absolute and relative login URLs:
            #   /accounts/login/
            #   /accounts/login/?next=...
            #   https://www182.lamp.le.ac.uk/accounts/login/?...
            if "accounts/login" in url:
                # Route user to your confirm-email landing instead of bouncing to login
                return redirect(reverse("account_email_verification_sent"))

        return response

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
