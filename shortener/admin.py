from django import forms
from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin, UserAdmin
from django.contrib.auth.models import Group, User
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.views.decorators.http import require_POST
from unfold.admin import ModelAdmin, TabularInline
from unfold.contrib.filters.admin import RangeDateFilter
from unfold.forms import AdminPasswordChangeForm, UserChangeForm, UserCreationForm

from shortener.metadata import fetch_url_params
from shortener.models import Domain, Link, Share
from shortener.share import build_share_urls


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
                "fields": [
                    "slug",
                    "target",
                    "desktop_target",
                    "domain",
                    "custom_tags",
                    "group",
                    "views",
                ],
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

    def get_readonly_fields(self, request, obj=None):
        # The share rewrites the targets on every save, so don't offer to edit them.
        if obj is not None and obj.share_id:
            return [*self.readonly_fields, "target", "desktop_target"]
        return self.readonly_fields

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


class ShareLinkForm(forms.ModelForm):
    class Meta:
        model = Link
        fields = ["share_platform", "slug"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["share_platform"].required = True
        # Every platform gets a slug picked by hand, not a random one.
        self.fields["slug"].initial = None


class ShareLinkFormSet(forms.BaseInlineFormSet):
    def clean(self):
        super().clean()

        share = self.instance
        # Unset when the share form itself is invalid; its errors come first.
        if not share.domain_id:
            return

        seen = set()

        for form in self.forms:
            if not form.cleaned_data or form.cleaned_data.get("DELETE"):
                continue

            platform = form.cleaned_data.get("share_platform")
            slug = form.cleaned_data.get("slug")

            error = platform and share.platform_error(platform)
            if error:
                form.add_error("share_platform", error)

            if not slug:
                continue
            slug = slug.lower()

            # Link has a (domain, slug) unique constraint, but the domain isn't
            # a field of this form, so the model validation skips it.
            clash = (
                Link.objects.filter(domain=share.domain, slug__iexact=slug)
                .exclude(pk=form.instance.pk)
                .exists()
            )
            if slug in seen or clash:
                form.add_error(
                    "slug",
                    ValidationError(
                        _("This slug is already used on %(domain)s."),
                        params={"domain": share.domain},
                    ),
                )
            seen.add(slug)


class ShareLinkInline(TabularInline):
    model = Link
    fk_name = "share"
    form = ShareLinkForm
    formset = ShareLinkFormSet
    fields = ["share_platform", "slug", "short_link", "views"]
    readonly_fields = ["short_link", "views"]
    extra = 0
    verbose_name = _("short link")
    verbose_name_plural = _("short links")

    @admin.display(description=_("short link"))
    def short_link(self, obj):
        if not obj.pk:
            return "-"
        url = obj.get_absolute_url()
        return format_html(
            '<a href="{}" target="_blank" rel="noopener">{}</a>', url, url
        )

    def has_view_permission(self, request, obj=None):
        return True

    def has_add_permission(self, request, obj=None):
        return True

    def has_change_permission(self, request, obj=None):
        return True

    def has_delete_permission(self, request, obj=None):
        return True


@admin.register(Share)
class ShareAdmin(ModelAdmin):
    list_display = ["__str__", "platforms", "domain", "created_at"]
    search_fields = ["text", "url", "links__slug"]
    date_hierarchy = "created_at"
    list_filter = [
        ("domain", admin.RelatedOnlyFieldListFilter),
        ("group", admin.RelatedOnlyFieldListFilter),
    ]

    autocomplete_fields = ["domain", "group"]
    inlines = [ShareLinkInline]

    fieldsets = (
        (None, {"fields": ["text", "url", "domain", "group"]}),
        (_("share links"), {"fields": ["share_links"]}),
    )
    readonly_fields = ["share_links"]

    class Media:
        js = ["shortener/share_preview.js"]

    @admin.display(description=_("platforms"))
    def platforms(self, obj):
        return ", ".join(link.get_share_platform_display() for link in obj.links.all())

    @admin.display(description=_("generated links"))
    def share_links(self, obj):
        return format_html(
            '<div id="share-preview" data-url="{}">{}</div>',
            reverse("admin:shortener_share_preview"),
            self._render_preview(obj.text, obj.url),
        )

    def _render_preview(self, text, url):
        return render_to_string(
            "shortener/share_preview.html",
            {"share_urls": build_share_urls(text, url), "empty": not (text or url)},
        )

    def get_urls(self):
        preview = self.admin_site.admin_view(require_POST(self.preview_view))
        return [
            path("preview/", preview, name="shortener_share_preview"),
            *super().get_urls(),
        ]

    def preview_view(self, request):
        """The generated links for unsaved text, so they update while typing."""
        return HttpResponse(
            self._render_preview(
                request.POST.get("text", "").strip(),
                request.POST.get("url", "").strip(),
            )
        )

    def save_formset(self, request, form, formset, change):
        if formset.model is not Link:
            return super().save_formset(request, form, formset, change)

        share = form.instance
        for link in formset.save(commit=False):
            share.apply_to(link)
            link.save()
        for link in formset.deleted_objects:
            link.delete()

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        # Links that weren't touched in the inline still carry the old text.
        form.instance.sync_links()

    def get_queryset(self, request):
        queryset = (
            super()
            .get_queryset(request)
            .select_related("domain")
            .prefetch_related("links")
        )
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
