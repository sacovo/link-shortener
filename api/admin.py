from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from rest_framework_api_key.admin import APIKeyModelAdmin
from rest_framework_api_key.models import APIKey
from unfold.admin import ModelAdmin

from .models import UserAPIKey

# Every key in this project belongs to a user, so the library's own unbound
# key model would only be a confusing second place to create keys.
admin.site.unregister(APIKey)


@admin.register(UserAPIKey)
class UserAPIKeyAdmin(APIKeyModelAdmin, ModelAdmin):
    list_display = [
        "prefix",
        "name",
        "user",
        "created",
        "expiry_date",
        "_has_expired",
        "revoked",
    ]
    list_filter = ["revoked", "created"]
    search_fields = ["name", "prefix", "user__username"]
    autocomplete_fields = ["user"]

    fieldsets = (
        (
            None,
            {
                "fields": ["name", "user"],
            },
        ),
        (
            _("validity"),
            {
                "fields": ["prefix", "expiry_date", "revoked"],
            },
        ),
    )

    def get_queryset(self, request):
        queryset = super().get_queryset(request).select_related("user")
        if request.user.is_superuser:
            return queryset
        # Users manage their own keys; only superusers see everyone's.
        return queryset.filter(user=request.user)

    def get_fieldsets(self, request, obj=None):
        if obj is None:
            # `prefix` only exists once the key has been generated.
            return (
                (None, {"fields": ["name", "user"]}),
                (_("validity"), {"fields": ["expiry_date"]}),
            )
        return super().get_fieldsets(request, obj)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "user" and not request.user.is_superuser:
            kwargs["queryset"] = type(request.user).objects.filter(pk=request.user.pk)
            kwargs["initial"] = request.user.pk
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
