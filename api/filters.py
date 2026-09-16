from django_filters import rest_framework as filters

from shortener.models import Link


class LinkFilter(filters.FilterSet):
    domain = filters.CharFilter(field_name="domain__domain_name", lookup_expr="iexact")
    group = filters.CharFilter(field_name="group__name", lookup_expr="iexact")
    slug = filters.CharFilter(lookup_expr="iexact")
    target = filters.CharFilter(lookup_expr="icontains")
    created_after = filters.IsoDateTimeFilter(
        field_name="created_at", lookup_expr="gte"
    )
    created_before = filters.IsoDateTimeFilter(
        field_name="created_at", lookup_expr="lte"
    )

    class Meta:
        model = Link
        fields = ["domain", "group", "slug", "target", "custom_tags"]
