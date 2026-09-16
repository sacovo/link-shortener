from django.contrib.auth.models import Group
from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from shortener.metadata import fetch_url_params
from shortener.models import Domain, Link, get_slug

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
