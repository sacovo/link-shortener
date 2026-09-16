from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _
from rest_framework_api_key.models import AbstractAPIKey, BaseAPIKeyManager


class UserAPIKeyManager(BaseAPIKeyManager):
    def get_usable_keys(self):
        return super().get_usable_keys().filter(user__is_active=True)


class UserAPIKey(AbstractAPIKey):
    """An API key that acts on behalf of a user.

    Tying keys to a user means the API reuses the same group based access
    rules as the admin: a key can only ever see what its owner can see.
    """

    objects = UserAPIKeyManager()

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="api_keys",
        verbose_name=_("user"),
        help_text=_("The key acts on behalf of this user."),
    )

    class Meta(AbstractAPIKey.Meta):
        verbose_name = _("API key")
        verbose_name_plural = _("API keys")

    def __str__(self):
        return f"{self.name} ({self.user})"
