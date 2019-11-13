from django.conf.urls import url
from .views import ProfileHomeView, ProfileIdentity

urlpatterns = [
    url(r'^$', ProfileHomeView.as_view(), name='profile-home'),
    url(r'^identity/(?P<pk>[0-9]+)/$',
        ProfileIdentity.as_view(), name='profile-identity-form'),
]