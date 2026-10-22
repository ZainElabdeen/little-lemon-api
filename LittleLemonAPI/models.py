from django.contrib.auth.models import User
from django.db import models, transaction


class Category(models.Model):
    slug = models.SlugField(max_length=100, unique=True)
    title = models.CharField(max_length=100, unique=True)

    class Meta:
        ordering = ["title"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.title


class MenuItem(models.Model):
    name = models.CharField(max_length=255)
    price = models.DecimalField(max_digits=6, decimal_places=2)
    description = models.TextField(blank=True)
    featured = models.BooleanField(default=False, db_index=True)
    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name="menu_items"
    )

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        with transaction.atomic():
            super().save(*args, **kwargs)
            if self.featured:
                MenuItem.objects.filter(featured=True).exclude(pk=self.pk).update(
                    featured=False
                )


class CartItem(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="cart_items")
    menu_item = models.ForeignKey(MenuItem, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=6, decimal_places=2)

    class Meta:
        ordering = ["id"]


class Order(models.Model):
    PENDING = 0
    DELIVERED = 1

    STATUS_CHOICES = [(0, "Pending"), (1, "Delivered")]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="orders")
    status = models.IntegerField(default=0, choices=STATUS_CHOICES)
    delivery_crew = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="delivery_orders",
    )
    total = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="order_items")
    menu_item = models.ForeignKey(MenuItem, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)
    price = models.DecimalField(max_digits=6, decimal_places=2)

    class Meta:
        ordering = ["id"]
