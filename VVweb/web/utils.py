# VVweb/web/utils.py
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
from django.contrib.staticfiles import finders
from weasyprint import HTML, CSS, default_url_fetcher
import logging

logger = logging.getLogger(__name__)


# -------------------------------------------------------------------
# INTERNAL: Safe static CSS loader
# -------------------------------------------------------------------
def _css(path):
    """
    Resolve a static file path into an absolute filesystem path for WeasyPrint.
    Raises a clear error if the file is missing.
    """
    resolved = finders.find(path)
    if not resolved:
        raise FileNotFoundError(f"Static file not found: {path}")
    return CSS(resolved)


# -------------------------------------------------------------------
# PDF RENDERING
# -------------------------------------------------------------------
def render_to_pdf(request, template_src, context_dict):
    """
    Generate a PDF using WeasyPrint from an HTML template.

    Key points:
    - Uses Django staticfiles to resolve CSS paths correctly
    - Avoids hardcoded filesystem assumptions
    - Works in dev, test, and production
    """
    html_string = render_to_string(template_src, context_dict)

    # MUST be a directory, not a URL
    base_url = settings.BASE_DIR

    pdf = HTML(
        string=html_string,
        url_fetcher=default_url_fetcher,
        base_url=base_url
    ).write_pdf(
        stylesheets=[
            _css("css/vvweb.css"),
            _css("vendor/bootstrap/css/bootstrap.css"),
            _css("vendor/bootstrap/css/bootstrap-grid.css"),
            _css("vendor/bootstrap/css/bootstrap-reboot.css"),
            _css("css/business-frontpage.css"),
        ],
        presentational_hints=True
    )

    return pdf


# -------------------------------------------------------------------
# FREE-TIER INFORMATIONAL SYNC
# -------------------------------------------------------------------
def sync_free_tier_quotas():
    """
    Informational helper only — real logic lives in signals + apps.
    """
    default_limit = getattr(settings, "DEFAULT_MONTHLY_VARIANT_ALLOWANCE", 20)

    logger.info(
        "[Free Tier Sync] "
        f"System free-tier allowance = {default_limit}. "
        "VariantQuota creation for all users is handled automatically "
        "by startup sync and user creation signals."
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
