from django.apps import AppConfig


class AccountsConfig(AppConfig):
    name = 'backend.apps.accounts'

    def ready(self):
        import backend.apps.accounts.signals  # noqa: F401
