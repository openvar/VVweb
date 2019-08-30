"""VVweb URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/2.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from web import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),
    path('help/about/', views.about, name='about'),
    path('help/contact/', views.contact, name='contact'),
    path('help/nomenclature/', views.nomenclature, name='nomenclature'),
    path('help/instructions/', views.instructions, name='batch_instructions'),
    path('service/validate/', views.validate, name='validate'),
    path('service/validate/batch/', views.batch_validate, name='batch_validate'),
    path('service/gene2trans/', views.genes_to_transcripts, name='genes2trans'),
    path('service/vcf2hgvs/', views.vcf2hgvs, name='vcf2hgvs'),
    path('download/<str:job_id>/', views.download_batch_res, name='batch_download'),
    path('accounts/', include('allauth.urls')),
    path('profile/', include('userprofiles.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
