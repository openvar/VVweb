from django.template.loader import render_to_string
from django.conf import settings
from weasyprint import HTML, CSS, default_url_fetcher


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

# <LICENSE>
# Copyright (C) 2016-2025 VariantValidator Contributors
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
