# web/middleware.py

from django.conf import settings
from django.http import HttpResponsePermanentRedirect

class SiteRedirectMiddleware:
    """
    When SITE_REDIRECT_ENABLED is True:
    - Everyone is redirected to SITE_REDIRECT_URL
    - EXCEPT users who have a valid bypass cookie
    - Bypass cookie is set once using a secret query token
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # If redirect mode is off, behave normally
        if not getattr(settings, "SITE_REDIRECT_ENABLED", False):
            return self.get_response(request)

        # ✅ Allow full site access if bypass cookie is present
        if request.COOKIES.get("site_bypass") == "1":
            return self.get_response(request)

        # ✅ One-time bypass token → set cookie and allow through
        token = request.GET.get("letmein")
        if token and token == getattr(settings, "SITE_REDIRECT_BYPASS_TOKEN", None):
            response = self.get_response(request)
            response.set_cookie(
                key="site_bypass",
                value="1",
                max_age=60 * 60 * 12,  # 12 hours
                httponly=True,
                secure=not settings.DEBUG,
                samesite="Lax",
            )
            return response

        # 🚫 Everyone else, every URL
        return HttpResponsePermanentRedirect(settings.SITE_REDIRECT_URL)

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
