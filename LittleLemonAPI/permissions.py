from rest_framework import permissions

MANAGER_GROUP = "Manager"
DELIVERY_CREW_GROUP = "Delivery crew"


def is_manager(user) -> bool:
    if not user or not user.is_authenticated:
        return False
    return user.is_superuser or user.groups.filter(name=MANAGER_GROUP).exists()


def is_delivery_crew(user) -> bool:
    if not user or not user.is_authenticated:
        return False
    return user.groups.filter(name=DELIVERY_CREW_GROUP).exists()


def is_customer(user) -> bool:
    if not user or not user.is_authenticated:
        return False
    return not is_manager(user) and not is_delivery_crew(user)


class IsManager(permissions.BasePermission):
    message = "This action is restricted to managers."

    def has_permission(self, request, view) -> bool:
        return is_manager(request.user)


class IsDeliveryCrew(permissions.BasePermission):
    message = "This action is restricted to delivery crew members."

    def has_permission(self, request, view) -> bool:
        return is_delivery_crew(request.user)


class IsCustomer(permissions.BasePermission):
    message = "This action is restricted to customers."

    def has_permission(self, request, view) -> bool:
        return is_customer(request.user)
