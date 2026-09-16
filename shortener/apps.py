from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class ShortenerConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "shortener"
    verbose_name = _("Shortener")
