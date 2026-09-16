from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin, UserAdmin
from django.contrib.auth.models import Group, User
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from unfold.admin import ModelAdmin
from unfold.contrib.filters.admin import RangeDateFilter
from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm

from shortener.metadata import fetch_url_params
from shortener.models import Domain, Link


@admin.register(Domain)
class DomainAdmin(ModelAdmin):
    search_fields = [
        "domain_name",
    ]

    list_display = ["domain_name", "link_count"]

    filter_vertical = [
        "groups",
    ]

    @admin.display(description=_("links"))
    def link_count(self, obj):
        return obj.link_set.count()

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if request.user.is_superuser:
            return queryset
        return queryset.filter(groups__user=request.user).distinct()

    def has_view_or_change_permission(self, request, obj=None):
        return True

    def has_view_permission(self, request, obj=None):
        return True

    def has_module_permission(self, request, obj=None):
        return True

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(Link)
class LinkAdmin(ModelAdmin):
    list_display = [
        "slug",
        "short_link",
        "target_link",
        "views",
        "domain",
        "custom_tags",
        "created_at",
    ]

    list_display_links = ["slug"]

    autocomplete_fields = ["domain", "group"]

    search_fields = ["slug", "title", "target"]
    date_hierarchy = "created_at"

    list_filter = [
        ("domain", admin.RelatedOnlyFieldListFilter),
        ("group", admin.RelatedOnlyFieldListFilter),
        "custom_tags",
        ("created_at", RangeDateFilter),
    ]
    list_filter_submit = True

    fieldsets = (
        (
            None,
            {
                "fields": ["slug", "target", "domain", "custom_tags", "group", "views"],
            },
        ),
        (
            _("custom tags"),
            {
                "fields": [
                    "title",
                    "og_title",
                    "og_type",
                    "og_description",
                    "og_image_url",
                    "og_image",
                    "og_image_width",
                    "og_image_height",
                    "og_url",
                    "twitter_card",
                    "twitter_site",
                    "twitter_creator",
                ],
                "classes": ("collapse",),
            },
        ),
    )

    readonly_fields = ["views"]

    @admin.display(description=_("short link"))
    def short_link(self, obj):
        url = obj.get_absolute_url()
        return format_html(
            '<a href="{}" target="_blank" rel="noopener">{}</a>', url, url
        )

    @admin.display(description=_("target"))
    def target_link(self, obj):
        target = obj.target
        label = target if len(target) <= 60 else target[:57] + "…"
        return format_html(
            '<a href="{}" target="_blank" rel="noopener">{}</a>', target, label
        )

    def save_model(self, request, obj, form, change):
        if not obj.pk and obj.custom_tags:
            for field, value in fetch_url_params(obj.target).items():
                # Don't clobber anything that was typed into the form.
                if not getattr(obj, field, None):
                    setattr(obj, field, value)

        super().save_model(request, obj, form, change)

    def get_queryset(self, request):
        queryset = super().get_queryset(request).select_related("domain", "group")
        if request.user.is_superuser:
            return queryset
        return queryset.filter(group__in=request.user.groups.all())

    def has_module_permission(self, request, obj=None):
        return True

    def has_view_or_change_permission(self, request, obj=None):
        return True

    def has_view_permission(self, request, obj=None):
        return True

    def has_add_permission(self, request):
        return True

    def has_change_permission(self, request, obj=None):
        return True

    def has_delete_permission(self, request, obj=None):
        return True


class CustomGroupAdmin(GroupAdmin, ModelAdmin):
    fields = [
        "name",
    ]

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if request.user.is_superuser:
            return queryset
        return queryset.filter(user=request.user)

    def has_add_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_module_permission(self, request, obj=None):
        return True

    def has_view_or_change_permission(self, request, obj=None):
        return True

    def has_view_permission(self, request, obj=None):
        return True


class CustomUserAdmin(UserAdmin, ModelAdmin):
    # Unfold ships styled replacements for the auth forms.
    form = UserChangeForm
    add_form = UserCreationForm
    change_password_form = AdminPasswordChangeForm


admin.site.unregister(Group)
admin.site.register(Group, CustomGroupAdmin)

admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)

admin.site.site_header = "Link shortener"
admin.site.site_title = "Link shortener"
