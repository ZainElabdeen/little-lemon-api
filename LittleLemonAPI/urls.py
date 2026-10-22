from django.urls import include, path

from .routers import LittleLemonRouter
from .views import (
    CartItemView,
    CategoryListView,
    DeliveryCrewUserViewSet,
    LittleLemonUserViewSet,
    ManagerUserViewSet,
    MenuItemViewSet,
    OrderViewSet,
)

router = LittleLemonRouter()
router.register("menu-items", MenuItemViewSet, basename="menu-items")
router.register("groups/manager/users", ManagerUserViewSet, basename="manager-users")
router.register("groups/delivery-crew/users", DeliveryCrewUserViewSet, basename="delivery-crew-users")
router.register("orders", OrderViewSet, basename="orders")
# The user viewset is mounted under `users/users` so that djoser's `me`
# action answers at /api/users/users/me/ while registration keeps its own
# explicit route at /api/users (see the urlpatterns below).
router.register("users/users", LittleLemonUserViewSet, basename="users")

urlpatterns = [
    path("", include(router.urls)),
    path("cart/menu-items", CartItemView.as_view(), name="cart-items"),
    path("cart/menu-items/", CartItemView.as_view(), name="cart-items-slash"),
    path("categories", CategoryListView.as_view(), name="categories"),
    path("categories/", CategoryListView.as_view(), name="categories-slash"),
    # Registration is bound to the `create` action explicitly: djoser picks
    # the user_create serializer from `self.action`, so the action has to be
    # named rather than routed through a generic view.
    path("users", LittleLemonUserViewSet.as_view({"post": "create"}), name="user-create"),
    path("users/", LittleLemonUserViewSet.as_view({"post": "create"}), name="user-create-slash"),
]
