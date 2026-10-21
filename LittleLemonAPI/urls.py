from django.urls import include, path

from .routers import LittleLemonRouter
from .views import MenuItemViewSet

router = LittleLemonRouter()
router.register("menu-items", MenuItemViewSet, basename="menu-items")

urlpatterns = [
    path("", include(router.urls)),
]
