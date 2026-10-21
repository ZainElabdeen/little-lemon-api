from rest_framework import permissions, status, viewsets
from rest_framework.response import Response

from .filters import MenuItemFilter
from .models import MenuItem
from .permissions import IsManager
from .serializers import MenuItemSerializer


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
