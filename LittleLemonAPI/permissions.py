"""Role helpers and DRF permission classes.

The group names live here and *only* here: the seed command, the serializers
and the views all import them from this module, so the two literals cannot
drift apart. (Migrations keep their own literals on purpose - a migration
must never import application code.)
"""

from rest_framework import permissions

MANAGER_GROUP = "manager"
DELIVERY_CREW_GROUP = "delivery_crew"


def is_manager(user) -> bool:
    """True for authenticated superusers and members of the manager group."""
    if not user or not user.is_authenticated:
        return False
    return user.is_superuser or user.groups.filter(name=MANAGER_GROUP).exists()


def is_delivery_crew(user) -> bool:
    """True for authenticated members of the delivery crew group."""
    if not user or not user.is_authenticated:
        return False
    return user.groups.filter(name=DELIVERY_CREW_GROUP).exists()


def is_customer(user) -> bool:
    """True for authenticated users who are neither managers nor delivery crew."""
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
