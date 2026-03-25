from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.accounts"

    def ready(self):
        import apps.accounts.signals
        from apps.accounts.invariants import connect_runtime_invariant_guard

        connect_runtime_invariant_guard()
