"""Serializers for the Little Lemon API.

`LittleLemonUserSerializer`, `LittleLemonCreateUserSerializer` and
`LittleLemonTokenSerializer` are wired into djoser through the ``DJOSER``
block in ``LittleLemon/settings.py``, so djoser renders *these* classes
instead of its own.
"""

from django.contrib.auth.models import User
from djoser.serializers import UserCreateSerializer
from rest_framework import serializers

from . import permissions
from .models import CartItem, MenuItem, Order, OrderItem


class MenuItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = MenuItem
        fields = ["id", "name", "price", "description", "category"]


class CartItemSerializer(serializers.ModelSerializer):
    """A cart row: the menu item is nested for reads, written by id."""

    menu_item = MenuItemSerializer(read_only=True)
    menu_item_id = serializers.PrimaryKeyRelatedField(
        source="menu_item", queryset=MenuItem.objects.all(), write_only=True
    )
    total = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = ["id", "menu_item", "menu_item_id", "quantity", "unit_price", "total"]
        # `unit_price` is a snapshot of the menu price taken when the item was
        # added, so it is never taken from the request body.
        read_only_fields = ["unit_price"]
        # DRF does not copy a model's default onto the serializer field, so
        # the model's `quantity` default is mirrored here (spec §5.3:
        # "quantity defaults to 1").
        extra_kwargs = {"quantity": {"default": 1}}

    def get_total(self, obj):
        return str(obj.unit_price * obj.quantity)


class OrderItemSerializer(serializers.ModelSerializer):
    menu_item = MenuItemSerializer(read_only=True)
    total = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = ["id", "menu_item", "quantity", "price", "total"]

    def get_total(self, obj):
        return str(obj.price * obj.quantity)


class DeliveryCrewField(serializers.Field):
    """A delivery-crew member, referenced by username or by numeric user id.

    Writing resolves the reference to a `User` who must be in the delivery
    crew group; reading renders the username (the human-meaningful form the
    client displays).
    """

    default_error_messages = {
        "unknown_user": "No user matches the given delivery crew reference.",
        "not_delivery_crew": "The selected user is not a member of the delivery crew group.",
    }

    def to_representation(self, value):
        return value.username if value else None

    def to_internal_value(self, data):
        if data is None or data == "":
            return None

        reference = str(data).strip()
        if not reference:
            return None

        # A numeric reference is a user id, anything else is a username.
        # `.filter(...).first()` is used deliberately: `get(pk=...)` raises
        # ValueError on a non-numeric pk, which would turn a bad payload into
        # a 500 instead of a 400. Only ASCII digits can be a user id:
        # `str.isdigit()` is also true for Unicode ordinal digits such as '²'
        # that `int()` rejects with a ValueError, so those fall through to
        # the username lookup and end as the ordinary "no such user" error.
        if reference.isascii() and reference.isdigit():
            user = User.objects.filter(pk=int(reference)).first()
        else:
            user = User.objects.filter(username=reference).first()

        if user is None:
            raise serializers.ValidationError(self.error_messages["unknown_user"])
        if not permissions.is_delivery_crew(user):
            raise serializers.ValidationError(self.error_messages["not_delivery_crew"])
        return user


class OrderSerializer(serializers.ModelSerializer):
    order_items = OrderItemSerializer(many=True, read_only=True)
    delivery_crew = DeliveryCrewField(required=False, allow_null=True)
    delivery_crew_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "user",
            "status",
            "delivery_crew",
            "delivery_crew_id",
            "total",
            "order_items",
            "created_at",
        ]
        read_only_fields = ["user", "total", "created_at"]


class GroupUserSerializer(serializers.ModelSerializer):
    """The public shape of a group member."""

    class Meta:
        model = User
        fields = ["id", "username", "email"]


class LittleLemonUserSerializer(serializers.ModelSerializer):
    """The user shape djoser renders, extended with role information."""

    groups = serializers.SerializerMethodField()
    is_manager = serializers.SerializerMethodField()
    is_delivery_crew = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "groups",
            "is_manager",
            "is_delivery_crew",
        ]
        read_only_fields = ["username"]

    def get_groups(self, obj):
        return [group.name for group in obj.groups.all()]

    def get_is_manager(self, obj):
        return permissions.is_manager(obj)

    def get_is_delivery_crew(self, obj):
        return permissions.is_delivery_crew(obj)


class LittleLemonCreateUserSerializer(UserCreateSerializer):
    """Registration payload: username, email, password and an optional name."""

    # djoser's own create serializer does not require the email address, so it
    # is declared here to make a missing email a 400 rather than a silently
    # discarded field.
    email = serializers.EmailField(required=True)
    name = serializers.CharField(required=False, allow_blank=True, write_only=True)

    class Meta(UserCreateSerializer.Meta):
        model = User
        fields = ["id", "username", "email", "password", "name"]

    def validate(self, attrs):
        # The parent validator builds `User(**attrs)`, which raises TypeError
        # on the extra `name` key, so it is stripped before the parent runs
        # and restored afterwards for `create()`.
        name = attrs.pop("name", None)
        attrs = super().validate(attrs)
        if name is not None:
            attrs["name"] = name
        return attrs

    def create(self, validated_data):
        name = validated_data.pop("name", "")
        user = super().create(validated_data)
        if name:
            user.first_name = name
            user.save(update_fields=["first_name"])
        return user


class LittleLemonTokenSerializer(serializers.Serializer):
    """The login response carries the token under both names clients expect."""

    token = serializers.CharField(source="key", read_only=True)
    auth_token = serializers.CharField(source="key", read_only=True)
