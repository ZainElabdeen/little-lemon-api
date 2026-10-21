from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from rest_framework import permissions, status, viewsets
from rest_framework.response import Response

from .filters import MenuItemFilter
from .models import MenuItem
from .pagination import LittleLemonPagination
from .permissions import DELIVERY_CREW_GROUP, MANAGER_GROUP, IsManager
from .serializers import GroupUserSerializer, MenuItemSerializer

User = get_user_model()


class MenuItemViewSet(viewsets.ModelViewSet):
    """Menu items: readable by any authenticated user, writable by managers only."""

    queryset = MenuItem.objects.all()
    serializer_class = MenuItemSerializer
    filterset_class = MenuItemFilter
    ordering_fields = ["id", "name", "price", "category"]
    ordering = ["id"]

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [permissions.IsAuthenticated()]
        return [IsManager()]

    def destroy(self, request, *args, **kwargs):
        """Delete a menu item and answer 200 (not DRF's default 204)."""
        instance = self.get_object()
        item_id = instance.pk
        self.perform_destroy(instance)
        return Response(
            {"detail": f"Menu item {item_id} was deleted."},
            status=status.HTTP_200_OK,
        )


class BaseGroupUserViewSet(viewsets.ViewSet):
    """Lists, adds and removes the members of one Django group."""

    group_name = ""
    permission_classes = [IsManager]

    def list(self, request):
        users = User.objects.filter(groups__name=self.group_name).order_by("id")
        paginator = LittleLemonPagination()
        page = paginator.paginate_queryset(users, request)
        if page is not None:
            return paginator.get_paginated_response(GroupUserSerializer(page, many=True).data)
        return Response(GroupUserSerializer(users, many=True).data)

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
        # `request.data` is whatever the client sent: a list or a string body
        # would blow up on `.get()`, so anything but a mapping is "not found".
        if not isinstance(payload, dict):
            return None
        username = payload.get("username")
        user_id = payload.get("user_id", payload.get("id"))
        if username:
            return User.objects.filter(username=str(username)).first()
        if user_id is not None:
            reference = str(user_id)
            # Only ASCII digits can be a user id: `int()` converts them without
            # raising, while `str.isdigit()` is also true for Unicode ordinal
            # digits such as '²' that `int()` rejects with a ValueError.
            # Anything else is treated as a username.
            if reference.isascii() and reference.isdigit():
                return User.objects.filter(pk=int(reference)).first()
            return User.objects.filter(username=reference).first()
        return None


class ManagerUserViewSet(BaseGroupUserViewSet):
    group_name = MANAGER_GROUP


class DeliveryCrewUserViewSet(BaseGroupUserViewSet):
    group_name = DELIVERY_CREW_GROUP
