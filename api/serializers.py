from django.contrib.auth.models import Group
from django.db import transaction
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from shortener.metadata import fetch_url_params
from shortener.models import Domain, Link, Share, get_free_slug, get_slug
from shortener.share import PLATFORM_CHOICES, build_share_urls

from .permissions import domains_for, groups_for

# Metadata the scraper is allowed to fill in when creating a link.
SCRAPED_FIELDS = (
    "title",
    "og_title",
    "og_type",
    "og_description",
    "og_image_url",
    "og_image_width",
    "og_image_height",
    "og_video_url",
    "og_video_width",
    "og_video_height",
    "og_url",
    "twitter_card",
    "twitter_site",
    "twitter_creator",
)


class GroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = ["id", "name"]


class DomainSerializer(serializers.ModelSerializer):
    class Meta:
        model = Domain
        fields = ["id", "domain_name"]


class LinkSerializer(serializers.ModelSerializer):
    domain = serializers.SlugRelatedField(
        slug_field="domain_name",
        queryset=Domain.objects.none(),
        help_text=_("Domain name the link is served from, e.g. `example.com`."),
    )
    group = serializers.SlugRelatedField(
        slug_field="name",
        queryset=Group.objects.none(),
        help_text=_("Name of the group that owns the link."),
    )
    slug = serializers.SlugField(
        required=False,
        help_text=_("Path of the short link. A random one is generated if omitted."),
    )
    short_url = serializers.CharField(source="get_absolute_url", read_only=True)
    custom_tags = serializers.BooleanField(
        required=False,
        # Explicit default: for form encoded requests DRF reads an absent
        # boolean as False (unchecked checkbox) unless the field has one, which
        # would quietly contradict the model default.
        default=True,
        help_text=_(
            "Serve a preview page carrying the open graph tags instead of "
            "redirecting straight to the target."
        ),
    )
    fetch_metadata = serializers.BooleanField(
        write_only=True,
        required=False,
        default=True,
        help_text=_(
            "Scrape the target for open graph tags and fill in any field you "
            "did not set yourself. Only applies when `custom_tags` is true."
        ),
    )

    class Meta:
        model = Link
        fields = [
            "id",
            "slug",
            "short_url",
            "target",
            "desktop_target",
            "domain",
            "group",
            "custom_tags",
            "views",
            "created_at",
            "fetch_metadata",
            "title",
            "og_title",
            "og_type",
            "og_description",
            "og_image_url",
            "og_image",
            "og_image_width",
            "og_image_height",
            "og_video_url",
            "og_video",
            "og_video_width",
            "og_video_height",
            "og_url",
            "twitter_card",
            "twitter_site",
            "twitter_creator",
        ]
        read_only_fields = ["id", "views", "created_at"]
        # The (domain, slug) UniqueConstraint would otherwise make `slug`
        # required and report the clash under `non_field_errors`; `validate`
        # below generates the slug and reports the clash on the field itself.
        validators = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Restrict the choosable domains and groups to what the caller may use,
        # which also gives DRF a sensible validation error for free.
        request = self.context.get("request")
        if request is not None and request.user.is_authenticated:
            self.fields["domain"].queryset = domains_for(request.user)
            self.fields["group"].queryset = groups_for(request.user)

    def validate_slug(self, value):
        return value.lower()

    def validate(self, attrs):
        domain = attrs.get("domain", getattr(self.instance, "domain", None))
        slug = attrs.get("slug")

        if slug is None and self.instance is None:
            slug = attrs["slug"] = get_slug()

        if slug is not None and domain is not None:
            clashes = Link.objects.filter(domain=domain, slug=slug)
            if self.instance is not None:
                clashes = clashes.exclude(pk=self.instance.pk)
            if clashes.exists():
                raise serializers.ValidationError(
                    {"slug": _("This slug is already used on this domain.")}
                )

        return attrs

    def create(self, validated_data):
        fetch_metadata = validated_data.pop("fetch_metadata", True)

        if fetch_metadata and validated_data.get("custom_tags", True):
            self._apply_scraped_metadata(validated_data)

        return super().create(validated_data)

    def update(self, instance, validated_data):
        validated_data.pop("fetch_metadata", None)
        return super().update(instance, validated_data)

    def _apply_scraped_metadata(self, validated_data):
        scraped = fetch_url_params(validated_data["target"])

        for field in SCRAPED_FIELDS:
            # Never overwrite something the caller set explicitly.
            if field in scraped and not validated_data.get(field):
                validated_data[field] = scraped[field]


class ShareLinkSerializer(serializers.ModelSerializer):
    platform = serializers.CharField(source="share_platform", read_only=True)
    short_url = serializers.CharField(source="get_absolute_url", read_only=True)

    class Meta:
        model = Link
        fields = [
            "id",
            "platform",
            "slug",
            "short_url",
            "target",
            "desktop_target",
            "views",
        ]
        read_only_fields = fields


class ShareSerializer(serializers.ModelSerializer):
    domain = serializers.SlugRelatedField(
        slug_field="domain_name",
        queryset=Domain.objects.none(),
        help_text=_(
            "Domain name the short links are served from. Can't be changed later."
        ),
    )
    group = serializers.SlugRelatedField(
        slug_field="name",
        queryset=Group.objects.none(),
        help_text=_("Name of the group that owns the share and its links."),
    )
    platforms = serializers.ListField(
        child=serializers.ChoiceField(choices=PLATFORM_CHOICES),
        write_only=True,
        required=False,
        allow_empty=False,
        help_text=_(
            "Create only: the platforms to make a short link for, one link each."
        ),
    )
    slug_prefix = serializers.SlugField(
        write_only=True,
        required=False,
        max_length=43,
        help_text=_(
            "Create only: slugs become `<prefix>-<random>`, e.g. `my-campaign-x3k9qa`. "
            "Without a prefix they are just the random part."
        ),
    )
    links = ShareLinkSerializer(many=True, read_only=True)
    short_urls = serializers.SerializerMethodField(
        help_text=_("Platform -> short URL, for picking one link by platform.")
    )

    class Meta:
        model = Share
        fields = [
            "id",
            "text",
            "url",
            "domain",
            "group",
            "platforms",
            "slug_prefix",
            "links",
            "short_urls",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        request = self.context.get("request")
        if request is not None and request.user.is_authenticated:
            self.fields["domain"].queryset = domains_for(request.user)
            self.fields["group"].queryset = groups_for(request.user)

    @extend_schema_field({"type": "object", "additionalProperties": {"type": "string"}})
    def get_short_urls(self, share):
        return {
            link.share_platform: link.get_absolute_url() for link in share.links.all()
        }

    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Links sort newest first by default; creation order follows `platforms`.
        data["links"].sort(key=lambda link: link["id"])
        return data

    def validate(self, attrs):
        if self.instance is None:
            platforms = attrs.get("platforms")
            if not platforms:
                raise serializers.ValidationError(
                    {"platforms": _("Name at least one platform.")}
                )
            if len(set(platforms)) != len(platforms):
                raise serializers.ValidationError(
                    {"platforms": _("Each platform can only be named once.")}
                )
        else:
            for field in ("platforms", "slug_prefix"):
                if field in attrs:
                    raise serializers.ValidationError(
                        {field: _("Can only be set when creating a share.")}
                    )
            if "domain" in attrs and attrs["domain"] != self.instance.domain:
                raise serializers.ValidationError(
                    {"domain": _("The domain of a share can't be changed.")}
                )
            platforms = self.instance.links.values_list("share_platform", flat=True)

        # An unsaved copy with the new values, to check the platforms against.
        share = Share(
            text=attrs.get("text", getattr(self.instance, "text", "")),
            url=attrs.get("url", getattr(self.instance, "url", "")),
        )
        errors = {
            platform: error
            for platform in platforms
            if (error := share.platform_error(platform))
        }
        if errors:
            raise serializers.ValidationError({"platforms": errors})

        return attrs

    @transaction.atomic
    def create(self, validated_data):
        platforms = validated_data.pop("platforms")
        prefix = validated_data.pop("slug_prefix", "")

        share = super().create(validated_data)
        for platform in platforms:
            share.add_link(platform, get_free_slug(share.domain, prefix))
        return share

    @transaction.atomic
    def update(self, instance, validated_data):
        share = super().update(instance, validated_data)
        share.sync_links()
        return share


class SharePreviewSerializer(serializers.Serializer):
    text = serializers.CharField(allow_blank=True, trim_whitespace=True)
    url = serializers.CharField(required=False, allow_blank=True, default="")
    platforms = serializers.ListField(
        child=serializers.ChoiceField(choices=PLATFORM_CHOICES),
        required=False,
        help_text=_("Only these platforms. All of them if omitted."),
    )


class SharePreviewLinkSerializer(serializers.Serializer):
    platform = serializers.ChoiceField(choices=PLATFORM_CHOICES)
    label = serializers.CharField()
    share_url = serializers.CharField(
        allow_null=True,
        help_text=_("Null when the platform can't share this, e.g. without a URL."),
    )
    desktop_url = serializers.CharField(
        allow_null=True,
        help_text=_("A better URL for desktop browsers, if the platform has one."),
    )


class SharePreviewResultSerializer(serializers.Serializer):
    text = serializers.CharField()
    url = serializers.CharField()
    links = SharePreviewLinkSerializer(many=True)

    @staticmethod
    def build(text, url, platforms=None):
        return {
            "text": text,
            "url": url,
            "links": [
                {
                    "platform": platform,
                    "label": str(label),
                    "share_url": share_url,
                    "desktop_url": desktop_url,
                }
                for platform, label, share_url, desktop_url in build_share_urls(
                    text, url
                )
                if not platforms or platform in platforms
            ],
        }


class LinkStatsSerializer(serializers.ModelSerializer):
    short_url = serializers.CharField(source="get_absolute_url", read_only=True)

    class Meta:
        model = Link
        fields = ["id", "slug", "short_url", "target", "views", "created_at"]
        read_only_fields = fields


class APIKeySerializer(serializers.Serializer):
    """The identity behind the key that made the request."""

    username = serializers.CharField(read_only=True)
    is_superuser = serializers.BooleanField(read_only=True)
    groups = serializers.ListField(child=serializers.CharField(), read_only=True)
    domains = serializers.ListField(child=serializers.CharField(), read_only=True)
