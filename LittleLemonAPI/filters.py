"""Query filters for the menu-item and order list endpoints (design spec §6)."""

import django_filters

from .models import MenuItem, Order


class MenuItemFilter(django_filters.FilterSet):
    """`?name=`, `?search=`, `?price_min=`, `?price_max=`, `?category=`, `?price=`."""

    name = django_filters.CharFilter(lookup_expr="icontains")
    # `search` is an alias for `name`; the lookup is `icontains` (there is no
    # `icontcontains` lookup in Django).
    search = django_filters.CharFilter(field_name="name", lookup_expr="icontains")
    price_min = django_filters.NumberFilter(field_name="price", lookup_expr="gte")
    price_max = django_filters.NumberFilter(field_name="price", lookup_expr="lte")

    class Meta:
        model = MenuItem
        fields = ["category", "price"]


class OrderFilter(django_filters.FilterSet):
    """`?delivery_crew=`, `?created_after=`, `?created_before=`, `?status=`."""

    delivery_crew = django_filters.CharFilter(
        field_name="delivery_crew__username", lookup_expr="iexact"
    )
    created_after = django_filters.IsoDateTimeFilter(
        field_name="created_at", lookup_expr="gte"
    )
    created_before = django_filters.IsoDateTimeFilter(
        field_name="created_at", lookup_expr="lte"
    )

    class Meta:
        model = Order
        fields = ["status"]
