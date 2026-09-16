from django.db import IntegrityError, transaction
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from shortener.metadata import fetch_url_params
from shortener.models import Link

from .filters import LinkFilter
from .permissions import domains_for, groups_for
from .serializers import (
    APIKeySerializer,
    DomainSerializer,
    GroupSerializer,
    LinkSerializer,
    SCRAPED_FIELDS,
)


@extend_schema(tags=["links"])
class LinkViewSet(viewsets.ModelViewSet):
    """Create, read, update and delete short links.

    Only links owned by one of your groups are visible.
    """

    serializer_class = LinkSerializer
    filterset_class = LinkFilter
    search_fields = ["slug", "title", "target"]
    ordering_fields = ["created_at", "views", "slug"]
    ordering = ["-created_at"]

    def get_queryset(self):
        queryset = Link.objects.select_related("domain", "group")

        user = self.request.user
        if user.is_superuser:
            return queryset

        return queryset.filter(group__in=user.groups.all())

    def perform_create(self, serializer):
        self._save(serializer)

    def perform_update(self, serializer):
        self._save(serializer)

    def _save(self, serializer):
        # `LinkSerializer.validate` already checks the slug, but two concurrent
        # calls can still both get past it and race into the DB constraint.
        try:
            with transaction.atomic():
                serializer.save()
        except IntegrityError as exc:
            data = serializer.validated_data
            clash = Link.objects.filter(
                domain=data.get("domain") or serializer.instance.domain,
                slug=data.get("slug") or serializer.instance.slug,
            )
            if not clash.exists():
                raise
            raise serializers.ValidationError(
                {"slug": _("This slug is already used on this domain.")}
            ) from exc

    @extend_schema(
        request=None,
        responses=LinkSerializer,
        summary=_("Re-scrape the target's open graph tags"),
    )
    @action(detail=True, methods=["post"], url_path="refresh-metadata")
    def refresh_metadata(self, request, pk=None):
        link = self.get_object()
        scraped = fetch_url_params(link.target)

        if not scraped:
            return Response(
                {"detail": _("No metadata could be read from the target.")},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        for field in SCRAPED_FIELDS:
            if field in scraped:
                setattr(link, field, scraped[field])
        link.save(update_fields=[f for f in SCRAPED_FIELDS if f in scraped])

        return Response(self.get_serializer(link).data)


@extend_schema(tags=["domains"])
class DomainViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    """The domains you may put short links on."""

    serializer_class = DomainSerializer
    search_fields = ["domain_name"]
    ordering_fields = ["domain_name"]
    ordering = ["domain_name"]

    def get_queryset(self):
        return domains_for(self.request.user)


@extend_schema(tags=["groups"])
class GroupViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    """The groups you may file short links under."""

    serializer_class = GroupSerializer
    search_fields = ["name"]
    ordering_fields = ["name"]
    ordering = ["name"]

    def get_queryset(self):
        return groups_for(self.request.user)


@extend_schema(
    tags=["identity"],
    responses=OpenApiResponse(APIKeySerializer),
    summary=_("Who this API key belongs to"),
)
class WhoAmIView(APIView):
    """Check a key and see what it may reach. Handy as an automation smoke test."""

    serializer_class = APIKeySerializer

    def get(self, request):
        user = request.user
        return Response(
            {
                "username": user.get_username(),
                "is_superuser": user.is_superuser,
                "groups": list(groups_for(user).values_list("name", flat=True)),
                "domains": list(
                    domains_for(user).values_list("domain_name", flat=True)
                ),
            }
        )
