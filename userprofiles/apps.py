from django.apps import AppConfig
from django.urls import reverse_lazy as _


class UserprofilesConfig(AppConfig):
    name = 'userprofiles'
    verbose_name = _(u'User profiles')

    def ready(self):
        from userprofiles import signals