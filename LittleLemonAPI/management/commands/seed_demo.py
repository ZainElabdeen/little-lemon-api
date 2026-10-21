"""Seed the Little Lemon demo data set.

The command is idempotent *and* declarative: re-running it restores the seeded
state exactly, including every seeded user's group membership. A task that
temporarily promotes a customer to manager can therefore re-run this command to
get back to the baseline instead of leaving the promoted membership behind.

Only ``admin`` is a superuser/staff member. Managers are group managers only
(``is_staff`` stays ``False``); the separate superuser covers Django-admin
access.
"""

from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.core.management.base import BaseCommand
from django.db import transaction

from LittleLemonAPI.models import CartItem, MenuItem, Order, OrderItem
from LittleLemonAPI.permissions import DELIVERY_CREW_GROUP, MANAGER_GROUP

# username, password, group names, is_staff, is_superuser
SEED_USERS = (
    ("admin", "AdminPass123!", (), True, True),
    ("customer1", "CustomerPass123!", (), False, False),
    ("customer2", "CustomerPass123!", (), False, False),
    ("manager1", "ManagerPass123!", (MANAGER_GROUP,), False, False),
    ("manager2", "ManagerPass123!", (MANAGER_GROUP,), False, False),
    ("crew1", "CrewPass123!", (DELIVERY_CREW_GROUP,), False, False),
    ("crew2", "CrewPass123!", (DELIVERY_CREW_GROUP,), False, False),
)

# name, price, description, category
SEED_MENU_ITEMS = (
    (
        "Greek Salad",
        Decimal("8.50"),
        "Fresh tomatoes, cucumber, olives and feta cheese.",
        "salads",
    ),
    (
        "Lemon Chicken",
        Decimal("13.75"),
        "Grilled chicken breast with lemon and herbs.",
        "mains",
    ),
    (
        "Veggie Wrap",
        Decimal("7.25"),
        "Grilled vegetables wrapped in a flatbread.",
        "mains",
    ),
    (
        "Lamb Burger",
        Decimal("11.00"),
        "Lamb patty with lettuce, tomato and mint sauce.",
        "mains",
    ),
    (
        "Strawberry Cheesecake",
        Decimal("6.50"),
        "Classic cheesecake topped with strawberries.",
        "desserts",
    ),
    (
        "Iced Tea",
        Decimal("3.00"),
        "Freshly brewed iced tea with a slice of lemon.",
        "drinks",
    ),
)


class Command(BaseCommand):
    help = "Create the Little Lemon demo accounts and menu items (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            dest="reset",
            help=(
                "Delete existing app data (cart items, order items, orders, menu "
                "items and non-superuser users) before seeding."
            ),
        )

    def handle(self, *args, **options):
        with transaction.atomic():
            if options["reset"]:
                self._reset()

            users_created, users_updated = self._seed_users()
            items_created, items_updated = self._seed_menu_items()

        self.stdout.write(self.style.SUCCESS("Seeded Little Lemon demo data."))
        self.stdout.write(
            f"  users: {users_created + users_updated} "
            f"({users_created} created, {users_updated} updated)"
        )
        self.stdout.write(
            f"  menu items: {items_created + items_updated} "
            f"({items_created} created, {items_updated} updated)"
        )

    def _reset(self):
        """Clear app data, keeping superusers (admin) in place."""
        # Count first: delete() also reports cascaded rows, which would blur
        # the per-model numbers.
        cart_items = CartItem.objects.count()
        order_items = OrderItem.objects.count()
        orders = Order.objects.count()
        menu_items = MenuItem.objects.count()
        users = User.objects.filter(is_superuser=False).count()

        CartItem.objects.all().delete()
        OrderItem.objects.all().delete()
        Order.objects.all().delete()
        MenuItem.objects.all().delete()
        User.objects.filter(is_superuser=False).delete()

        self.stdout.write(
            f"Reset: deleted cart items {cart_items}, order items {order_items}, "
            f"orders {orders}, menu items {menu_items}, non-superuser users {users}."
        )

    def _seed_users(self):
        """Create/update the seeded accounts and set their groups declaratively."""
        groups = {
            name: Group.objects.get_or_create(name=name)[0]
            for name in (MANAGER_GROUP, DELIVERY_CREW_GROUP)
        }

        created_count = 0
        updated_count = 0

        for username, password, group_names, is_staff, is_superuser in SEED_USERS:
            user, created = User.objects.get_or_create(username=username)
            if created:
                created_count += 1
            else:
                updated_count += 1

            user.email = f"{username}@littlelemon.example"
            user.is_staff = is_staff
            user.is_superuser = is_superuser
            user.set_password(password)
            user.save()

            # Declarative: the user's groups are exactly the seeded ones - any
            # extra membership (e.g. a customer temporarily promoted to manager)
            # is removed again.
            user.groups.set([groups[name] for name in group_names])

        return created_count, updated_count

    def _seed_menu_items(self):
        """Create/update the seeded menu items."""
        created_count = 0
        updated_count = 0

        for name, price, description, category in SEED_MENU_ITEMS:
            existing = MenuItem.objects.filter(name=name)
            item = existing.first()

            if item is None:
                item = MenuItem(name=name)
                created_count += 1
            else:
                updated_count += 1

            item.price = price
            item.description = description
            item.category = category
            item.save()

            # Collapse duplicate rows that share a seeded name.
            existing.exclude(pk=item.pk).delete()

        return created_count, updated_count
