from django.template.loader import render_to_string
from django.conf import settings
from weasyprint import HTML, CSS, default_url_fetcher
from web.models import VariantQuota


"""
 Utility to control rendering of validation results into a PDF version
"""


def render_to_pdf(request, template_src, context_dict):
    """Generate pdf using weasyprint HTML"""
    html_string = render_to_string(template_src, context_dict)
    pdf = HTML(string=html_string, url_fetcher=default_url_fetcher, base_url=request.build_absolute_uri()).write_pdf(
        stylesheets=[CSS(settings.BASE_DIR + '/web/static/css/vvweb.css'),
                     CSS(settings.BASE_DIR + '/web/static/vendor/bootstrap/css/bootstrap.css'),
                     CSS(settings.BASE_DIR + '/web/static/vendor/bootstrap/css/bootstrap-grid.css'),
                     CSS(settings.BASE_DIR + '/web/static/vendor/bootstrap/css/bootstrap-reboot.css'),
                     CSS(settings.BASE_DIR + '/web/static/css/business-frontpage.css')
                     ],
        presentational_hints=True)
    return pdf

def sync_free_tier_quotas():
    """
    Update all Free-tier users' max_allowance to match the current
    DEFAULT_MONTHLY_VARIANT_ALLOWANCE in settings.py / local_settings.py.
    Does NOT touch users who already have a higher limit (Pro/Enterprise).
    """
    default_limit = getattr(settings, "DEFAULT_MONTHLY_VARIANT_ALLOWANCE", 20)

    # Free-tier users are those whose max_allowance is <= default
    free_users = VariantQuota.objects.filter(max_allowance__lte=default_limit)

    updated_count = free_users.update(max_allowance=default_limit)
    print(f"Updated {updated_count} Free-tier users to max_allowance = {default_limit}")

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
