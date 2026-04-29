# VVweb/web/middleware.py

from django.conf import settings
from django.http import HttpResponseRedirect


class SiteRedirectMiddleware:
    """
    Behaviour:

    When SITE_REDIRECT_ENABLED = False:
        ✅ No redirect ever
        ✅ Force-delete bypass cookie every request

    When SITE_REDIRECT_ENABLED = True:
        ✅ Allow access if bypass cookie exists
        ✅ Allow one-time token bypass
        ✅ Otherwise redirect (TEMPORARY redirect only)

    Notes:
        - Uses HttpResponseRedirect (302) to avoid browser caching issues
        - Cookie deletion is unconditional and matches original flags
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        # --------------------------------------------------
        # 🔥 HARD OFF SWITCH (no redirect, kill cookie)
        # --------------------------------------------------
        if not getattr(settings, "SITE_REDIRECT_ENABLED", False):
            response = self.get_response(request)

            # 🔥 ALWAYS delete the bypass cookie (no condition)
            response.delete_cookie(
                key="site_bypass",
                path="/",          # must match set_cookie
            )

            return response

        # --------------------------------------------------
        # ✅ Allow if bypass cookie already present
        # --------------------------------------------------
        if request.COOKIES.get("site_bypass") == "1":
            return self.get_response(request)

        # --------------------------------------------------
        # ✅ One-time bypass via secret token
        # --------------------------------------------------
        token = request.GET.get("letmein")

        if token and token == getattr(settings, "SITE_REDIRECT_BYPASS_TOKEN", None):
            response = self.get_response(request)

            response.set_cookie(
                key="site_bypass",
                value="1",
                path="/",                     # MUST match delete_cookie
                max_age=60 * 60 * 12,        # 12 hours
                httponly=True,
                secure=not settings.DEBUG,
                samesite="Lax",
            )

            return response

        # --------------------------------------------------
        # 🚫 Redirect everyone else (TEMPORARY redirect only)
        # --------------------------------------------------
        return HttpResponseRedirect(settings.SITE_REDIRECT_URL)

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
