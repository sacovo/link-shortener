from django.utils.translation import gettext as _

import requests
from django.contrib import admin
from django.contrib.auth.models import Group
from django.contrib.auth.admin import GroupAdmin
from shortener.models import Link, Domain

from bs4 import BeautifulSoup

# Register your models here.
def fetch_url_params(url):
    html = BeautifulSoup(requests.get(url).text)
    mapping = {
        ("og:title", "og_title"),
        ("og:type", "og_type"),
        ("og:description", "og_description"),
        ("og:image", "og_image"),
        ("og:image:width", "og_image_width"),
        ("og:image:height", "og_image_height"),
        ("og:video", "og_video_url"),
        ("og:video:width", "og_video_url_width"),
        ("og:video:height", "og_video_url_height"),
        ("og:url", "og_url"),
        ("twitter:card", "twitter_card"),
        ("twitter:site", "twitter_site"),
    }
    result = {}

    for m in mapping:
        e = html.head.find("meta", attrs={"property": m[0]})
        if e:
            result.update({m[1]: e["content"]})
    e = html.head.find("title")
    if e:
        result.update({"title": e.text})
    return result


@admin.register(Domain)
class DomainAdmin(admin.ModelAdmin):
    search_fields = [
        "domain_name",
    ]

    list_display = ["domain_name"]

    filter_vertical = [
        "groups",
    ]

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if request.user.is_superuser:
            return queryset
        return queryset.filter(groups__user=request.user)

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
class LinkAdmin(admin.ModelAdmin):

    list_display = [
        "slug",
        "domain",
        "get_absolute_url",
        "target",
        "custom_tags",
    ]

    autocomplete_fields = ["domain", "group"]

    search_fields = ["slug", "title"]
    date_hierarchy = "created_at"

    list_filter = [
        ("domain", admin.RelatedOnlyFieldListFilter),
        ("group", admin.RelatedOnlyFieldListFilter),
    ]

    fieldsets = (
        (None, {"fields": ["slug", "target", "domain", "custom_tags", "group"],}),
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

    def save_model(self, request, obj, form, change):
        obj.slug = obj.slug.lower()
        if not obj.pk and obj.custom_tags:
            tags = fetch_url_params(obj.target)

            for tag in tags:
                obj.__dict__.update({tag: tags[tag]})

        super().save_model(request, obj, form, change)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
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


class CustomGroupAdmin(GroupAdmin):

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


admin.site.unregister(Group)
admin.site.register(Group, CustomGroupAdmin)

admin.site.site_header = "Link shortener"
admin.site.site_title = "Link shortener"
