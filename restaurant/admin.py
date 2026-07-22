from django.contrib import admin
from .models import Category, Dish, Order, OrderItem
class DishInline(admin.TabularInline):
    model = Dish
    extra = 0
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [DishInline]

@admin.register(Dish)
class DishAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'price', 'is_available')
    list_filter = ('category', 'is_available')
    search_fields = ('name',)
    
class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('dish_name', 'price', 'quantity')

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'customer_name', 'phone', 'status',
        'total_price', 'created_at',
    )
    list_filter = ('status', 'created_at')
    search_fields = ('customer_name', 'phone', 'address')
    inlines = [OrderItemInline]