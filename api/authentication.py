from django.utils.translation import gettext_lazy as _
from rest_framework import authentication, exceptions
from rest_framework_api_key.permissions import KeyParser

from .models import UserAPIKey


class APIKeyAuthentication(authentication.BaseAuthentication):
    """Authenticate with ``Authorization: Api-Key <key>``.

    Resolves the key to its owning user so that the rest of the API can use
    the ordinary ``request.user`` group checks.
    """

    keyword = KeyParser.keyword
    key_parser = KeyParser()

    def authenticate(self, request):
        key = self.key_parser.get(request)

        if not key:
            return None

        try:
            api_key = UserAPIKey.objects.get_from_key(key)
        except UserAPIKey.DoesNotExist:
            raise exceptions.AuthenticationFailed(_("Invalid API key."))

        if api_key.has_expired:
            raise exceptions.AuthenticationFailed(_("API key has expired."))

        return api_key.user, api_key

    def authenticate_header(self, request):
        return self.keyword
