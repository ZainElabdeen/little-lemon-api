from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.core.cache import cache
from rest_framework import status
from rest_framework.test import APITestCase

from .models import CartItem, Category, MenuItem, Order
from .permissions import DELIVERY_CREW_GROUP, MANAGER_GROUP


class GradingCriteriaTests(APITestCase):
    @classmethod
    def setUpTestData(cls):
        cls.manager_group = Group.objects.get(name=MANAGER_GROUP)
        cls.crew_group = Group.objects.get(name=DELIVERY_CREW_GROUP)

        cls.admin = User.objects.create_superuser("admin", "admin@example.com", "AdminPass123!")
        cls.manager = User.objects.create_user("manager1", "m@example.com", "ManagerPass123!")
        cls.manager.groups.add(cls.manager_group)
        cls.crew = User.objects.create_user("crew1", "c@example.com", "CrewPass123!")
        cls.crew.groups.add(cls.crew_group)
        cls.customer = User.objects.create_user("customer1", "u@example.com", "CustomerPass123!")

        cls.mains = Category.objects.create(slug="mains", title="Mains")
        cls.desserts = Category.objects.create(slug="desserts", title="Desserts")
        cls.items = [
            MenuItem.objects.create(name=f"Main {i}", price=Decimal(10 + i), category=cls.mains)
            for i in range(4)
        ] + [
            MenuItem.objects.create(name="Cake", price=Decimal("2.50"), category=cls.desserts)
        ]

    def setUp(self):
        cache.clear()

    def login(self, username, password):
        response = self.client.post(
            "/token/login/", {"username": username, "password": password}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        return response.data["auth_token"]

    def as_user(self, user):
        self.client.force_authenticate(user)

    def place_order(self):
        self.as_user(self.customer)
        self.client.post("/api/cart/menu-items", {"menu_item_id": self.items[0].id, "quantity": 2})
        response = self.client.post("/api/orders")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        return response.data["id"]

    def test_01_admin_assigns_user_to_manager_group(self):
        self.as_user(self.admin)
        response = self.client.post("/api/groups/manager/users", {"username": "customer1"})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(self.customer.groups.filter(name=MANAGER_GROUP).exists())

    def test_02_admin_token_accesses_manager_group(self):
        token = self.login("admin", "AdminPass123!")
        response = self.client.get(
            "/api/groups/manager/users", HTTP_AUTHORIZATION=f"Token {token}"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([u["username"] for u in response.data["results"]], ["manager1"])

    def test_03_admin_adds_menu_item(self):
        self.as_user(self.admin)
        response = self.client.post(
            "/api/menu-items",
            {"name": "Soup", "price": "5.00", "category_id": self.mains.id},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["category"]["slug"], "mains")

    def test_04_admin_adds_category(self):
        self.as_user(self.admin)
        response = self.client.post("/api/categories", {"title": "Starters"})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(response.data["slug"], "starters")

    def test_04_non_manager_cannot_add_category(self):
        self.as_user(self.customer)
        response = self.client.post("/api/categories", {"title": "Starters"})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_05_manager_logs_in(self):
        self.assertTrue(self.login("manager1", "ManagerPass123!"))

    def test_06_manager_updates_item_of_the_day(self):
        self.items[1].featured = True
        self.items[1].save()
        self.as_user(self.manager)
        response = self.client.patch(
            f"/api/menu-items/{self.items[0].id}", {"featured": True}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        featured = list(MenuItem.objects.filter(featured=True).values_list("id", flat=True))
        self.assertEqual(featured, [self.items[0].id])

    def test_06_customer_cannot_update_item_of_the_day(self):
        self.as_user(self.customer)
        response = self.client.patch(
            f"/api/menu-items/{self.items[0].id}", {"featured": True}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_07_manager_assigns_user_to_delivery_crew(self):
        self.as_user(self.manager)
        response = self.client.post("/api/groups/delivery-crew/users", {"username": "customer1"})
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(self.customer.groups.filter(name=DELIVERY_CREW_GROUP).exists())

    def test_08_manager_assigns_order_to_delivery_crew(self):
        order_id = self.place_order()
        self.as_user(self.manager)
        response = self.client.patch(
            f"/api/orders/{order_id}", {"delivery_crew": self.crew.id}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(Order.objects.get(pk=order_id).delivery_crew, self.crew)

    def test_09_delivery_crew_sees_assigned_orders(self):
        assigned = self.place_order()
        self.place_order()
        Order.objects.filter(pk=assigned).update(delivery_crew=self.crew)
        self.as_user(self.crew)
        response = self.client.get("/api/orders")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([o["id"] for o in response.data["results"]], [assigned])

    def test_10_delivery_crew_marks_order_delivered(self):
        order_id = self.place_order()
        Order.objects.filter(pk=order_id).update(delivery_crew=self.crew)
        self.as_user(self.crew)
        response = self.client.patch(f"/api/orders/{order_id}", {"status": 1}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Order.objects.get(pk=order_id).status, Order.DELIVERED)
        response = self.client.patch(
            f"/api/orders/{order_id}", {"delivery_crew": None}, format="json"
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_11_customer_registers(self):
        response = self.client.post(
            "/api/users",
            {"username": "newbie", "email": "n@example.com", "password": "Sup3rSecret!x"},
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)

    def test_12_customer_logs_in_and_uses_token(self):
        token = self.login("customer1", "CustomerPass123!")
        response = self.client.get("/api/users/users/me/", HTTP_AUTHORIZATION=f"Token {token}")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["username"], "customer1")

    def test_13_customer_browses_categories(self):
        self.as_user(self.customer)
        response = self.client.get("/api/categories")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([c["slug"] for c in response.data["results"]], ["desserts", "mains"])

    def test_14_customer_browses_all_menu_items(self):
        self.as_user(self.customer)
        response = self.client.get("/api/menu-items")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], len(self.items))

    def test_15_customer_browses_menu_items_by_category(self):
        self.as_user(self.customer)
        for value in ("desserts", "Desserts", str(self.desserts.id)):
            response = self.client.get("/api/menu-items", {"category": value})
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual([i["name"] for i in response.data["results"]], ["Cake"])

    def test_16_customer_paginates_menu_items(self):
        self.as_user(self.customer)
        response = self.client.get("/api/menu-items", {"page": 2, "page_size": 2})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 2)
        self.assertIsNotNone(response.data["next"])
        self.assertIsNotNone(response.data["previous"])

    def test_17_customer_sorts_menu_items_by_price(self):
        self.as_user(self.customer)
        response = self.client.get("/api/menu-items", {"ordering": "-price"})
        prices = [Decimal(i["price"]) for i in response.data["results"]]
        self.assertEqual(prices, sorted(prices, reverse=True))

    def test_18_customer_adds_item_to_cart(self):
        self.as_user(self.customer)
        response = self.client.post(
            "/api/cart/menu-items", {"menu_item_id": self.items[0].id, "quantity": 3}
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        self.assertEqual(CartItem.objects.get(user=self.customer).quantity, 3)

    def test_19_customer_sees_cart(self):
        CartItem.objects.create(
            user=self.customer, menu_item=self.items[0], quantity=1, unit_price=Decimal("10")
        )
        self.as_user(self.customer)
        response = self.client.get("/api/cart/menu-items")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)

    def test_20_customer_places_order(self):
        order_id = self.place_order()
        order = Order.objects.get(pk=order_id)
        self.assertEqual(order.total, Decimal("20.00"))
        self.assertEqual(order.order_items.count(), 1)
        self.assertFalse(CartItem.objects.filter(user=self.customer).exists())

    def test_21_customer_browses_own_orders(self):
        own = self.place_order()
        other = User.objects.create_user("customer2", "o@example.com", "CustomerPass123!")
        Order.objects.create(user=other)
        self.as_user(self.customer)
        response = self.client.get("/api/orders")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual([o["id"] for o in response.data["results"]], [own])

    def test_anonymous_requests_are_rejected(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get("/api/menu-items").status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(self.client.get("/api/categories").status_code, status.HTTP_401_UNAUTHORIZED)
