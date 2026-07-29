from django.contrib import admin
from .models import (
    Category, Dish, Order, OrderItem, Profile, Igridients, RecipeItem, StockMovement,
    SupportConversation, SupportMessage,
)
from .forms import RecipeItemForm

class DishInline(admin.TabularInline):
    model = Dish
    extra = 0


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'slug')
    prepopulated_fields = {'slug': ('name',)}
    inlines = [DishInline]


class RecipeItemInline(admin.TabularInline):
    model = RecipeItem
    form = RecipeItemForm
    extra = 3


@admin.register(Dish)
class DishAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'price', 'is_available')
    list_filter = ('category', 'is_available')
    search_fields = ('name',)
    inlines = [RecipeItemInline]


@admin.register(Igridients)
class IgridientsAdmin(admin.ModelAdmin):
    list_display = ('name', 'unit', 'stock_quantity')
    list_filter = ('unit',)
    search_fields = ('name',)
    list_editable = ('unit',)

    def get_readonly_fields(self, request, obj=None):
        # Остаток меняется только через StockMovement (приход / ревизия).
        # При создании ингредиента начальный остаток можно задать.
        if obj is not None:
            return ('stock_quantity',)
        return ()


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ('ingredient', 'quantity', 'reason', 'created_by', 'created_at')
    list_filter = ('reason', 'created_at')
    search_fields = ('ingredient__name', 'note')
    readonly_fields = ('created_by', 'created_at')
    autocomplete_fields = ('ingredient',)

    def has_add_permission(self, request):
        # Приход / ревизия — через кабинет бухгалтера.
        return False

    def save_model(self, request, obj, form, change):
        if not change and obj.created_by_id is None:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


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


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'is_active')
    list_filter = ('role', 'is_active')
    search_fields = ('user__username', 'user__email')
    list_editable = ('role', 'is_active')


class SupportMessageInline(admin.TabularInline):
    model = SupportMessage
    extra = 0
    readonly_fields = ('sender', 'text', 'is_from_support', 'created_at')
    can_delete = False


@admin.register(SupportConversation)
class SupportConversationAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'agent', 'status', 'updated_at')
    list_filter = ('status', 'updated_at')
    search_fields = ('user__username', 'agent__username')
    inlines = [SupportMessageInline]
