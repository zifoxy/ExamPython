import csv

from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.http import HttpResponse
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.utils.http import url_has_allowed_host_and_scheme

from decimal import Decimal
from collections import defaultdict

from .models import Category, Dish, Order, OrderItem, Profile, Igridients, StockMovement
from .cart import Cart
from .forms import OrderCreateForm, DishForm, RegisterForm, RevisionForm, MovementPeriodForm
from .decorators import role_required
from .stock_reports import build_revision_blank_rows


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

    if not request.user.is_authenticated:
        messages.info(request, 'Войдите, чтобы оформить заказ и видеть его в личном кабинете')
        return redirect(f"{reverse('login')}?next={reverse('order_create')}")

    if request.method == 'POST':
        form = OrderCreateForm(request.POST)
        if form.is_valid():
            order = form.save(commit=False)
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
        form = OrderCreateForm(initial={
            'customer_name': request.user.get_full_name() or request.user.username,
        })

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
            return redirect('cabinet')
    else:
        form = RegisterForm()

    return render(request, 'restaurant/register.html', {'form': form})


@login_required
def cabinet(request):
    profile = getattr(request.user, 'profile', None)
    orders = (
        Order.objects
        .filter(user=request.user)
        .prefetch_related('items')
        .order_by('-created_at')
    )
    cart = Cart(request)
    return render(request, 'restaurant/cabinet.html', {
        'profile': profile,
        'orders': orders,
        'cart': cart,
    })


@login_required
def order_detail(request, order_id):
    order = get_object_or_404(
        Order.objects.prefetch_related('items'),
        pk=order_id,
        user=request.user,
    )
    return render(request, 'restaurant/order_detail.html', {
        'order': order,
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


#Бухгалтер

@role_required(Profile.ROLE_ACCOUNTANT)
def accountant_ingredients(request):
    ingredients = Igridients.objects.all()
    dishes = Dish.objects.select_related('category').prefetch_related('recipe_items').order_by('name')
    return render(request, 'restaurant/accountant/ingredients.html', {
        'ingredients': ingredients,
        'dishes': dishes,
    })


@role_required(Profile.ROLE_ACCOUNTANT)
def accountant_revision(request, pk):
    ingredient = get_object_or_404(Igridients, pk=pk)
    if request.method == 'POST':
        form = RevisionForm(request.POST)
        if form.is_valid():
            StockMovement.create_revision(
                ingredient=ingredient,
                actual_quantity=form.cleaned_data['actual_quantity'],
                user=request.user,
                note=form.cleaned_data.get('note', ''),
            )
            messages.success(
                request,
                f'Ревизия «{ingredient.name}»: остаток = {form.cleaned_data["actual_quantity"]} {ingredient.unit}',
            )
            return redirect('accountant_ingredients')
    else:
        form = RevisionForm(initial={'actual_quantity': ingredient.stock_quantity})

    return render(request, 'restaurant/accountant/revision.html', {
        'ingredient': ingredient,
        'form': form,
    })


@role_required(Profile.ROLE_ACCOUNTANT)
def accountant_recipe(request, pk):
    dish = get_object_or_404(
        Dish.objects.prefetch_related('recipe_items__igridients'),
        pk=pk,
    )
    return render(request, 'restaurant/accountant/recipe.html', {
        'dish': dish,
        'recipe_items': dish.recipe_items.select_related('igridients'),
    })


@role_required(Profile.ROLE_ACCOUNTANT)
def accountant_consumption(request):
    """Расход ингредиентов по выполненным заказам (рецептура × порции)."""
    order_items = (
        OrderItem.objects
        .filter(order__status='done', dish__isnull=False)
        .select_related('dish')
        .prefetch_related('dish__recipe_items__igridients')
    )
    totals = defaultdict(lambda: {
        'name': '',
        'unit': '',
        'quantity': Decimal('0'),
    })
    for oi in order_items:
        for ri in oi.dish.recipe_items.all():
            ing = ri.igridients
            totals[ing.pk]['name'] = ing.name
            totals[ing.pk]['unit'] = ing.unit
            totals[ing.pk]['quantity'] += ri.quantity * oi.quantity

    rows = sorted(totals.values(), key=lambda r: r['name'].lower())
    return render(request, 'restaurant/accountant/consumption.html', {
        'rows': rows,
    })


@role_required(Profile.ROLE_ACCOUNTANT)
def accountant_revision_blank(request):
    form = MovementPeriodForm(request.GET or None)
    rows = []
    if form.is_valid():
        rows = build_revision_blank_rows(
            form.cleaned_data['date_from'],
            form.cleaned_data['date_to'],
        )
    return render(request, 'restaurant/accountant/revision_blank.html', {
        'form': form,
        'rows': rows,
    })


@role_required(Profile.ROLE_ACCOUNTANT)
def accountant_revision_blank_export(request):
    form = MovementPeriodForm(request.GET or None)
    if not form.is_valid():
        messages.error(request, 'Укажите корректный период дат')
        return redirect('accountant_revision_blank')

    date_from = form.cleaned_data['date_from']
    date_to = form.cleaned_data['date_to']
    rows = build_revision_blank_rows(date_from, date_to)

    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = (
        f'attachment; filename="revision_{date_from}_{date_to}.csv"'
    )
    writer = csv.writer(response, delimiter=';')
    writer.writerow([
        'Ингредиент', 'Ед.', 'На начало', 'Приход (+)', 'Расход (−)',
        'Учёт на конец', 'Факт', 'Разница',
    ])
    for row in rows:
        writer.writerow([
            row['name'],
            row['unit'],
            row['stock_start'],
            row['plus'],
            row['minus'],
            row['stock_end'],
            '',
            '',
        ])
    return response
