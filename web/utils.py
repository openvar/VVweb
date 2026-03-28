# web/utils.py
#
# Utility functions for VariantValidator
# ------------------------
# - PDF rendering (WeasyPrint)
# - Free-tier sync (informational)
#
# IMPORTANT:
# Creation of VariantQuota rows and assignment of the free-tier plan
# is handled automatically by:
#   • web/signals.py       (for NEW users)
#   • web/apps.py          (for EXISTING users at startup)
#
# This file intentionally does NOT attempt to modify user quotas
# because the correct logic now resides in signals + apps.
# ------------------------

from django.template.loader import render_to_string
from django.conf import settings
from weasyprint import HTML, CSS, default_url_fetcher
import logging

logger = logging.getLogger("vv")


# -------------------------------------------------------------------
# PDF RENDERING
# -------------------------------------------------------------------
def render_to_pdf(request, template_src, context_dict):
    """
    Generate a PDF using WeasyPrint from an HTML template.
    """
    html_string = render_to_string(template_src, context_dict)

    base_url = request.build_absolute_uri()  # ensures correct paths for CSS/images

    pdf = HTML(
        string=html_string,
        url_fetcher=default_url_fetcher,
        base_url=base_url
    ).write_pdf(
        stylesheets=[
            CSS(settings.BASE_DIR + "/web/static/css/vvweb.css"),
            CSS(settings.BASE_DIR + "/web/static/vendor/bootstrap/css/bootstrap.css"),
            CSS(settings.BASE_DIR + "/web/static/vendor/bootstrap/css/bootstrap-grid.css"),
            CSS(settings.BASE_DIR + "/web/static/vendor/bootstrap/css/bootstrap-reboot.css"),
            CSS(settings.BASE_DIR + "/web/static/css/business-frontpage.css"),
        ],
        presentational_hints=True,
    )

    return pdf


# -------------------------------------------------------------------
# FREE-TIER INFORMATIONAL SYNC
# -------------------------------------------------------------------
def sync_free_tier_quotas():
    """
    This function previously attempted to directly modify database
    rows to enforce free-tier limits. As the system has evolved,
    that logic has been moved to:
        • web/signals.py  (for new users)
        • web/apps.py     (for existing users at startup)

    Therefore, this function now serves only as an informational
    helper that logs the current free-tier allowance.

    Its presence maintains backwards compatibility with any admin
    scripts or management commands that might still call it.
    """
    default_limit = getattr(settings, "DEFAULT_MONTHLY_VARIANT_ALLOWANCE", 20)

    logger.info(
        f"[Free Tier Sync] "
        f"System free-tier allowance = {default_limit}. "
        f"VariantQuota creation for all users is handled automatically "
        f"by startup sync and user creation signals."
    )

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
