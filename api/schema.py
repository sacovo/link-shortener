"""drf-spectacular extensions, imported from ``ApiConfig.ready``."""

from drf_spectacular.extensions import OpenApiAuthenticationExtension


class APIKeyAuthenticationScheme(OpenApiAuthenticationExtension):
    target_class = "api.authentication.APIKeyAuthentication"
    name = "ApiKeyAuth"

    def get_security_definition(self, auto_schema):
        return {
            "type": "apiKey",
            "in": "header",
            "name": "Authorization",
            "description": (
                "An API key created in the admin, sent as "
                "`Authorization: Api-Key <prefix>.<secret>`."
            ),
        }
