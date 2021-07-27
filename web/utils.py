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



