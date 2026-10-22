from decimal import Decimal

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import transaction
from django.db.models import ProtectedError
from django.http import Http404
from django.shortcuts import get_object_or_404
from djoser import views as djoser_views
from rest_framework import permissions, status, viewsets
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, ScopedRateThrottle, UserRateThrottle
from rest_framework.views import APIView

from .filters import MenuItemFilter, OrderFilter
from .models import CartItem, Category, MenuItem, Order, OrderItem
from .pagination import LittleLemonPagination
from .permissions import (
    DELIVERY_CREW_GROUP,
    MANAGER_GROUP,
    IsCustomer,
    IsDeliveryCrew,
    IsManager,
    is_delivery_crew,
    is_manager,
)
from .serializers import (
    CartItemSerializer,
    CategorySerializer,
    GroupUserSerializer,
    MenuItemSerializer,
    OrderSerializer,
)

User = get_user_model()


def paginated_response(queryset, serializer_class, request):
    paginator = LittleLemonPagination()
    page = paginator.paginate_queryset(queryset, request)
    if page is not None:
        return paginator.get_paginated_response(serializer_class(page, many=True).data)
    return Response(serializer_class(queryset, many=True).data)


class MenuItemViewSet(viewsets.ModelViewSet):
    queryset = MenuItem.objects.select_related("category")
    serializer_class = MenuItemSerializer
    filterset_class = MenuItemFilter
    ordering_fields = ["id", "name", "price", "featured", "category__title"]
    ordering = ["id"]

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [permissions.IsAuthenticated()]
        return [IsManager()]

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        item_id = instance.pk
        self.perform_destroy(instance)
        return Response(
            {"detail": f"Menu item {item_id} was deleted."},
            status=status.HTTP_200_OK,
        )


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    filterset_fields = ["slug"]
    ordering_fields = ["id", "slug", "title"]
    ordering = ["title"]

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [permissions.IsAuthenticated()]
        return [IsManager()]

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        category_id = instance.pk
        try:
            self.perform_destroy(instance)
        except ProtectedError:
            return Response(
                {"detail": "This category still has menu items and cannot be deleted."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            {"detail": f"Category {category_id} was deleted."},
            status=status.HTTP_200_OK,
        )


class BaseGroupUserViewSet(viewsets.ViewSet):
    group_name = ""
    permission_classes = [IsManager]

    def list(self, request):
        users = User.objects.filter(groups__name=self.group_name).order_by("id")
        return paginated_response(users, GroupUserSerializer, request)

    def create(self, request):
        user = self._resolve_user(request.data)
        if user is None:
            return Response(
                {"detail": "Provide a valid 'username' or 'user_id' in the payload."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if user.groups.filter(name=self.group_name).exists():
            return Response(
                {"detail": f"{user.username} is already in the {self.group_name} group."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        user.groups.add(Group.objects.get(name=self.group_name))
        return Response(GroupUserSerializer(user).data, status=status.HTTP_201_CREATED)

    def destroy(self, request, pk=None):
        user = self._resolve_user({"user_id": pk})
        if user is None or not user.groups.filter(name=self.group_name).exists():
            return Response(
                {"detail": f"No user in the {self.group_name} group matches {pk!r}."},
                status=status.HTTP_404_NOT_FOUND,
            )
        user.groups.remove(Group.objects.get(name=self.group_name))
        return Response(
            {"detail": f"{user.username} was removed from the {self.group_name} group."}
        )

    def _resolve_user(self, payload):
        if not isinstance(payload, dict):
            return None
        username = payload.get("username")
        user_id = payload.get("user_id", payload.get("id"))
        if username:
            return User.objects.filter(username=str(username)).first()
        if user_id is not None:
            reference = str(user_id)
            if reference.isascii() and reference.isdigit():
                return User.objects.filter(pk=int(reference)).first()
            return User.objects.filter(username=reference).first()
        return None


class ManagerUserViewSet(BaseGroupUserViewSet):
    group_name = MANAGER_GROUP


class DeliveryCrewUserViewSet(BaseGroupUserViewSet):
    group_name = DELIVERY_CREW_GROUP


class CartItemView(APIView):
    permission_classes = [IsCustomer]

    def get(self, request):
        items = CartItem.objects.filter(user=request.user).select_related("menu_item")
        return paginated_response(items, CartItemSerializer, request)

    def post(self, request):
        serializer = CartItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        menu_item = serializer.validated_data["menu_item"]
        cart_item = CartItem.objects.create(
            user=request.user,
            menu_item=menu_item,
            quantity=serializer.validated_data["quantity"],
            unit_price=menu_item.price,
        )
        return Response(
            CartItemSerializer(cart_item).data, status=status.HTTP_201_CREATED
        )

    def delete(self, request):
        deleted, _ = CartItem.objects.filter(user=request.user).delete()
        return Response({"detail": "Cart cleared.", "deleted": deleted})


class OrderViewSet(viewsets.ModelViewSet):
    serializer_class = OrderSerializer
    filterset_class = OrderFilter
    ordering_fields = ["id", "status", "total", "created_at"]
    ordering = ["-created_at"]

    def get_permissions(self):
        if self.action == "create":
            return [IsCustomer()]
        if self.action == "destroy":
            return [IsManager()]
        if self.action in ("update", "partial_update"):
            if is_manager(self.request.user):
                return [IsManager()]
            if is_delivery_crew(self.request.user):
                return [IsDeliveryCrew()]
            return [IsManager()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        user = self.request.user
        if is_manager(user):
            return Order.objects.all().select_related("delivery_crew")
        if is_delivery_crew(user):
            return Order.objects.filter(delivery_crew=user).select_related("delivery_crew")
        return Order.objects.filter(user=user).select_related("delivery_crew")

    def get_object(self):
        try:
            order = get_object_or_404(Order, pk=self.kwargs["pk"])
        except (TypeError, ValueError):
            raise Http404(
                f"No {Order._meta.object_name} matches the given query."
            ) from None
        self.check_order_access(order)
        return order

    def check_order_access(self, order):
        user = self.request.user
        if is_manager(user):
            return
        if is_delivery_crew(user):
            if order.delivery_crew_id != user.id:
                raise PermissionDenied(
                    "This order is assigned to a different delivery crew member."
                )
            return
        if order.user_id != user.id:
            raise PermissionDenied("This order does not belong to you.")

    def create(self, request, *args, **kwargs):
        cart_items = list(
            CartItem.objects.filter(user=request.user).select_related("menu_item")
        )
        if not cart_items:
            return Response(
                {"detail": "Your cart is empty. Add items before placing an order."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        total = Decimal("0.00")
        for cart_item in cart_items:
            total += cart_item.unit_price * cart_item.quantity
        if total > Decimal("999999.99"):
            return Response(
                {"detail": "Order total exceeds the maximum allowed amount."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        with transaction.atomic():
            order = Order.objects.create(user=request.user, status=Order.PENDING)
            order_items = []
            for cart_item in cart_items:
                order_items.append(
                    OrderItem(
                        order=order,
                        menu_item=cart_item.menu_item,
                        quantity=cart_item.quantity,
                        price=cart_item.unit_price,
                    )
                )
            OrderItem.objects.bulk_create(order_items)
            order.total = total
            order.save(update_fields=["total", "updated_at"])
            CartItem.objects.filter(user=request.user).delete()
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        order = self.get_object()
        if is_delivery_crew(request.user) and request.method == "PUT":
            raise ValidationError(
                {"detail": "Delivery crew may only PATCH the 'status' field."}
            )
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        order = self.get_object()
        if is_delivery_crew(request.user):
            self._validate_crew_payload(request)
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        order = self.get_object()
        order_id = order.id
        order.delete()
        return Response({"detail": f"Order {order_id} was deleted."})

    def _validate_crew_payload(self, request):
        if not isinstance(request.data, dict):
            raise ValidationError(
                {"detail": "Expected an object with a 'status' field."}
            )
        offending = sorted(set(request.data.keys()) - {"status"})
        if offending:
            raise ValidationError(
                {
                    "detail": "Delivery crew may only update the 'status' field. "
                    f"Rejected: {', '.join(offending)}."
                }
            )


class LittleLemonUserViewSet(djoser_views.UserViewSet):
    pass


class LittleLemonTokenCreateView(djoser_views.TokenCreateView):
    throttle_scope = "login"
    throttle_classes = [AnonRateThrottle, UserRateThrottle, ScopedRateThrottle]


class LittleLemonTokenLogoutView(djoser_views.TokenDestroyView):
    throttle_scope = "login"
    throttle_classes = [AnonRateThrottle, UserRateThrottle, ScopedRateThrottle]
