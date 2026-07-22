from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.utils.http import url_has_allowed_host_and_scheme

from .models import Category, Dish, Order, OrderItem, Profile
from .cart import Cart
from .forms import OrderCreateForm, DishForm, RegisterForm
from .decorators import role_required


def _safe_redirect_url(request, fallback='menu'):
    """Разрешаем redirect только на свои URL."""
    next_url = request.POST.get('next') or request.GET.get('next')
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return next_url
    return reverse(fallback)


def _parse_quantity(value, default=1):
    try:
        quantity = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, quantity)


def menu(request):
    categories = Category.objects.prefetch_related('dishes').all()
    return render(request, 'restaurant/menu.html', {
        'categories': categories,
    })


def dish_detail(request, pk):
    dish = get_object_or_404(Dish, pk=pk, is_available=True)
    return render(request, 'restaurant/dish_detail.html', {'dish': dish})


@require_POST
def cart_add(request, dish_id):
    cart = Cart(request)
    dish = get_object_or_404(Dish, id=dish_id, is_available=True)
    quantity = _parse_quantity(request.POST.get('quantity', 1))
    cart.add(dish.id, quantity)
    messages.success(request, f'«{dish.name}» добавлено в корзину')
    return redirect(_safe_redirect_url(request))


@require_POST
def cart_remove(request, dish_id):
    cart = Cart(request)
    cart.remove(dish_id)
    return redirect('cart_detail')


@require_POST
def cart_update(request, dish_id):
    cart = Cart(request)
    quantity = _parse_quantity(request.POST.get('quantity', 1))
    cart.update(dish_id, quantity)
    return redirect('cart_detail')


def cart_detail(request):
    cart = Cart(request)
    return render(request, 'restaurant/cart.html', {'cart': cart})


def order_create(request):
    cart = Cart(request)
    if len(cart) == 0:
        messages.warning(request, 'Корзина пуста')
        return redirect('menu')

    if request.method == 'POST':
        form = OrderCreateForm(request.POST)
        if form.is_valid():
            order = form.save(commit=False)
            if request.user.is_authenticated:
                order.user = request.user
            order.total_price = cart.get_total_price()
            order.save()
            for item in cart:
                OrderItem.objects.create(
                    order=order,
                    dish=item['dish'],
                    dish_name=item['dish'].name,
                    price=item['price'],
                    quantity=item['quantity'],
                )
            cart.clear()
            return redirect('order_success', order_id=order.id)
    else:
        form = OrderCreateForm()

    return render(request, 'restaurant/checkout.html', {
        'cart': cart,
        'form': form,
    })


def order_success(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    if (
        order.user_id
        and request.user.is_authenticated
        and order.user_id != request.user.id
        and not request.user.is_superuser
    ):
        messages.error(request, 'Нет доступа к этому заказу')
        return redirect('cabinet')
    return render(request, 'restaurant/order_success.html', {
        'order_id': order.id,
    })


def register(request):
    if request.user.is_authenticated:
        return redirect('cabinet')

    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Регистрация успешна')
            return redirect('menu')
    else:
        form = RegisterForm()

    return render(request, 'restaurant/register.html', {'form': form})


@login_required
def cabinet(request):
    orders = Order.objects.filter(user=request.user).prefetch_related('items')
    profile = getattr(request.user, 'profile', None)
    return render(request, 'restaurant/cabinet.html', {
        'orders': orders,
        'profile': profile,
    })


@role_required(Profile.ROLE_MODERATOR)
def dish_create(request):
    if request.method == 'POST':
        form = DishForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, 'Блюдо успешно создано')
            return redirect('menu')
    else:
        form = DishForm()

    return render(request, 'restaurant/moderator/dish_form.html', {
        'form': form,
        'title': 'Добавить блюдо',
    })


@role_required(Profile.ROLE_MODERATOR)
def dish_edit(request, pk):
    dish = get_object_or_404(Dish, pk=pk)
    if request.method == 'POST':
        form = DishForm(request.POST, request.FILES, instance=dish)
        if form.is_valid():
            form.save()
            messages.success(request, 'Блюдо успешно обновлено')
            return redirect('menu')
    else:
        form = DishForm(instance=dish)

    return render(request, 'restaurant/moderator/dish_form.html', {
        'form': form,
        'title': f'Редактировать: {dish.name}',
    })


@role_required(Profile.ROLE_MODERATOR)
def dish_delete(request, pk):
    dish = get_object_or_404(Dish, pk=pk)
    if request.method == 'POST':
        name = dish.name
        dish.delete()
        messages.success(request, f'Блюдо «{name}» удалено')
        return redirect('menu')
    return render(request, 'restaurant/moderator/dish_confirm_delete.html', {
        'dish': dish,
    })
