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


"""
<!-- Bootstrap core CSS -->
<link href="{% static 'vendor/bootstrap/css/bootstrap.min.css' %}" rel="stylesheet">

<!-- Custom styles for this template -->
<link href="{% static 'css/business-frontpage.css' %}" rel="stylesheet">

<link href="{% static 'css/vvweb.css' %}" rel="stylesheet">
<link href="{% static 'cookielaw/css/cookielaw.css' %}" rel="stylesheet">

<script src="https://kit.fontawesome.com/ff8a38ffc2.js" crossorigin="anonymous"></script>

<!-- Favicon -->
<link rel="apple-touch-icon" sizes="180x180" href="{% static 'img/favicon/apple-touch-icon.png' %}">
<link rel="icon" type="image/png" sizes="32x32" href="{% static 'img/favicon/favicon-32x32.png' %}">
<link rel="icon" type="image/png" sizes="16x16" href="{% static 'img/favicon/favicon-16x16.png' %}">
<link rel="manifest" href="{% static 'img/favicon/site.webmanifest' %}">

<!-- Bootstrap core JavaScript -->
<script src="https://code.jquery.com/jquery-3.4.1.min.js" integrity="sha256-CSXorXvZcTkaix6Yvo6HppcZGetbYMGWSFlBw8HfCJo=" crossorigin="anonymous"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/popper.js/1.14.7/umd/popper.min.js" integrity="sha384-UO2eT0CpHqdSJQ6hJty5KVphtPhzWj9WO1clHTMGa3JDZwrnQq4sF86dIHNDz0W1" crossorigin="anonymous"></script>
<script src="https://stackpath.bootstrapcdn.com/bootstrap/4.3.1/js/bootstrap.min.js" integrity="sha384-JjSmVgyd0p3pXB1rRibZUAYoIIy6OrQ6VrjIEaFf/nJGzIxFDsf4x0xIM+B07jRM" crossorigin="anonymous"></script>
<script src="{% static 'js/cookielaw.js' %}"></script>
<script src="{% static 'js/vvweb.js' %}"></script>
"""
