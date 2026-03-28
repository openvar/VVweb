# VVweb/urls.py

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from web import views, views_quota, views_resend
from web.views import StyledEmailSentView, StyledSignupView, StrictLoginView
# from verification.views_banned import banned_landing  # <-- remove this

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),
    path('help/about/', views.about, name='about'),
    path('help/contact/', views.contact, name='contact'),
    path('help/nomenclature/', views.nomenclature, name='nomenclature'),
    path('help/instructions/', views.instructions, name='batch_instructions'),
    path('help/faq/', views.faqs, name='faqs'),
    path('service/validate/', views.validate, name='validate'),
    path('service/validate/batch/', views.batch_validate, name='batch_validate'),
    path('service/gene2trans/', views.genes_to_transcripts, name='genes2trans'),
    path('download/<str:job_id>/', views.download_batch_res, name='batch_download'),
    path('bed/', views.bed_file, name='bed'),
    path("accounts/resend-confirmation/", views_resend.resend_confirmation, name="resend_confirmation"),
    path("accounts/login/", StrictLoginView.as_view(), name="account_login"),
    path('accounts/signup/', StyledSignupView.as_view(), name='account_signup'),
    path("accounts/confirm-email/", StyledEmailSentView.as_view(), name="account_email_verification_sent"),

    # Verification routes (verify/, verify/pending/, commercial/, banned/)
    path("", include("verification.urls")),

    # Allauth account routes (no social if social apps are removed)
    path('accounts/', include('allauth.urls')),

    path("quota/", views_quota.quota_status, name="quota_status"),
    path('profile/', include('userprofiles.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

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
