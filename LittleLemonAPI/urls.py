from django.urls import include, path

from .routers import LittleLemonRouter
from .views import DeliveryCrewUserViewSet, ManagerUserViewSet, MenuItemViewSet

router = LittleLemonRouter()
router.register("menu-items", MenuItemViewSet, basename="menu-items")
router.register("groups/manager/users", ManagerUserViewSet, basename="manager-users")
router.register("groups/delivery-crew/users", DeliveryCrewUserViewSet, basename="delivery-crew-users")

urlpatterns = [
    path("", include(router.urls)),
]
