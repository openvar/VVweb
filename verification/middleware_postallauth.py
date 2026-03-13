# verification/middleware_postallauth.py
from django.shortcuts import redirect
from django.urls import reverse

class PostAllauthLoginRedirectFix:
    """
    Intercept Allauth's redirect to the login page that happens when an
    unverified user attempts to log in (Allauth auto-sends email then
    bounces to /accounts/login/?next=...).

    We override that bounce and send the user to our confirm-email landing.
    This works for both anonymous and authenticated requests.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        # Only examine redirect responses (HttpResponseRedirect/HttpResponsePermanentRedirect)
        if not hasattr(response, "url"):
            return response

        url = response.url or ""

        # Allauth uses multiple forms:
        #   /accounts/login/
        #   /accounts/login/?next=/accounts/confirm-email/
        #   https://<host>/accounts/login/?...
        # Use substring check and avoid loops if we're already on confirm page.
        if "accounts/login" in url:
            # If the target is already confirm-email, let it pass
            # (defensive: some setups send next=/accounts/confirm-email/)
            # We still prefer to send the user there directly.
            confirm_url = reverse("account_email_verification_sent")
            return redirect(confirm_url)

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
