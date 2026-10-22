from django.contrib import admin

from .models import CartItem, Category, MenuItem, Order, OrderItem


class CategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "slug")
    prepopulated_fields = {"slug": ("title",)}


class MenuItemAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "price", "category", "featured")
    list_editable = ("featured",)
    search_fields = ("name", "category__title")
    list_filter = ("category", "featured")


class CartItemAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "menu_item", "quantity", "unit_price")


class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "status", "delivery_crew", "total", "created_at")
    list_filter = ("status",)


class OrderItemAdmin(admin.ModelAdmin):
    list_display = ("id", "order", "menu_item", "quantity", "price")


admin.site.register(Category, CategoryAdmin)
admin.site.register(MenuItem, MenuItemAdmin)
admin.site.register(CartItem, CartItemAdmin)
admin.site.register(Order, OrderAdmin)
admin.site.register(OrderItem, OrderItemAdmin)
