# verification/middleware_postallauth.py

from django.shortcuts import redirect
from django.urls import reverse

class PostAllauthLoginRedirectFix:
    """
    Fix Allauth auto-redirecting unverified users back to /accounts/login/
    after auto-sending a confirmation email, by redirecting them instead
    to /accounts/confirm-email/.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        response = self.get_response(request)

        # Only care about redirects
        if hasattr(response, "url"):
            url = response.url

            # Case 1: Allauth bounced user back to login *after* auto-send
            if url.startswith("/accounts/login"):

                # Only intervene if the user is logged in already
                if request.user.is_authenticated:
                    # Route user to your email confirmation page instead
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
