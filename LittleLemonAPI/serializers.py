from django.contrib.auth.models import User
from django.utils.text import slugify
from djoser.serializers import UserCreateSerializer
from rest_framework import serializers

from . import permissions
from .models import CartItem, Category, MenuItem, Order, OrderItem


class CategorySerializer(serializers.ModelSerializer):
    slug = serializers.SlugField(max_length=100, required=False)

    class Meta:
        model = Category
        fields = ["id", "slug", "title"]

    def validate(self, attrs):
        if not attrs.get("slug") and attrs.get("title"):
            attrs["slug"] = slugify(attrs["title"])
        if not attrs.get("slug") and self.instance is None:
            raise serializers.ValidationError({"title": "A title that yields a slug is required."})
        slug = attrs.get("slug")
        if slug and Category.objects.filter(slug=slug).exclude(
            pk=getattr(self.instance, "pk", None)
        ).exists():
            raise serializers.ValidationError({"slug": "A category with this slug already exists."})
        return attrs


class MenuItemSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        source="category", queryset=Category.objects.all(), write_only=True
    )

    class Meta:
        model = MenuItem
        fields = ["id", "name", "price", "description", "featured", "category", "category_id"]


class CartItemSerializer(serializers.ModelSerializer):
    menu_item = MenuItemSerializer(read_only=True)
    menu_item_id = serializers.PrimaryKeyRelatedField(
        source="menu_item", queryset=MenuItem.objects.all(), write_only=True
    )
    total = serializers.SerializerMethodField()

    class Meta:
        model = CartItem
        fields = ["id", "menu_item", "menu_item_id", "quantity", "unit_price", "total"]
        read_only_fields = ["unit_price"]
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
    class Meta:
        model = User
        fields = ["id", "username", "email"]


class LittleLemonUserSerializer(serializers.ModelSerializer):
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
    email = serializers.EmailField(required=True)
    name = serializers.CharField(required=False, allow_blank=True, write_only=True)

    class Meta(UserCreateSerializer.Meta):
        model = User
        fields = ["id", "username", "email", "password", "name"]

    def validate(self, attrs):
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
    token = serializers.CharField(source="key", read_only=True)
    auth_token = serializers.CharField(source="key", read_only=True)
