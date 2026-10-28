from django.apps import AppConfig


class MarketingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "marketing"
    verbose_name = "Marketing & advertising"

    def ready(self):
        from django.contrib.auth.signals import user_logged_in

        from .signals import restore_bag
        user_logged_in.connect(restore_bag, dispatch_uid="marketing_restore_bag")
