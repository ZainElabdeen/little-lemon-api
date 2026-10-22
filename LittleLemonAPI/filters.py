import django_filters

from .models import MenuItem, Order


class MenuItemFilter(django_filters.FilterSet):
    name = django_filters.CharFilter(lookup_expr="icontains")
    search = django_filters.CharFilter(field_name="name", lookup_expr="icontains")
    price_min = django_filters.NumberFilter(field_name="price", lookup_expr="gte")
    price_max = django_filters.NumberFilter(field_name="price", lookup_expr="lte")

    class Meta:
        model = MenuItem
        fields = ["category", "price"]


class OrderFilter(django_filters.FilterSet):
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
