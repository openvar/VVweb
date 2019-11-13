from django.apps import AppConfig


class UserprofilesConfig(AppConfig):
    name = 'userprofiles'

    def ready(self):
        from userprofiles import signals
