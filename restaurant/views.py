import csv

from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.http import HttpResponse, JsonResponse
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db import transaction
from django.db.models import Sum, Count
from django.db.models.functions import TruncDate
from django.utils.http import url_has_allowed_host_and_scheme

from decimal import Decimal
from collections import defaultdict

from .models import (
    Category, Dish, Order, OrderItem, Profile, Igridients, StockMovement,
    SupportConversation, SupportMessage,
)
from .cart import Cart
from .forms import (
    OrderCreateForm,
    OrderStatusForm,
    DishForm,
    RegisterForm,
    RevisionForm,
    MovementPeriodForm,
    RecipeItemFormSet,
    PurchaseLineFormSet,
    StockMovementEditForm,
    SupportMessageForm,
)
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


def terms_of_use(request):
    return render(request, 'restaurant/terms_of_use.html')


def dish_detail(request, pk):
    dish = get_object_or_404(
        Dish.objects.select_related('category').prefetch_related('recipe_items__igridients'),
        pk=pk,
        is_available=True,
    )
    composition = [
        item.igridients.name
        for item in dish.recipe_items.all()
        if item.igridients_id
    ]
    return render(request, 'restaurant/dish_detail.html', {
        'dish': dish,
        'composition': composition,
    })


def _redirect_guests_to_register(request):
    if request.user.is_authenticated:
        return None
    messages.warning(request, 'Зарегистрируйтесь, прежде чем сделать заказ')
    return redirect('register')


@require_POST
def cart_add(request, dish_id):
    deny = _redirect_guests_to_register(request)
    if deny:
        return deny

    cart = Cart(request)
    dish = get_object_or_404(Dish, id=dish_id, is_available=True)
    quantity = _parse_quantity(request.POST.get('quantity', 1))
    cart.add(dish.id, quantity)
    messages.success(request, f'«{dish.name}» добавлено в корзину')
    return redirect(_safe_redirect_url(request))


@require_POST
def cart_remove(request, dish_id):
    deny = _redirect_guests_to_register(request)
    if deny:
        return deny
    cart = Cart(request)
    cart.remove(dish_id)
    return redirect('cart_detail')


@require_POST
def cart_update(request, dish_id):
    deny = _redirect_guests_to_register(request)
    if deny:
        return deny
    cart = Cart(request)
    quantity = _parse_quantity(request.POST.get('quantity', 1))
    cart.update(dish_id, quantity)
    return redirect('cart_detail')


def cart_detail(request):
    deny = _redirect_guests_to_register(request)
    if deny:
        return deny
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
            request.session['pending_checkout'] = {
                'customer_name': form.cleaned_data['customer_name'],
                'phone': form.cleaned_data['phone'],
                'address': form.cleaned_data['address'],
                'comment': form.cleaned_data.get('comment') or '',
                'total_price': str(cart.get_total_price()),
                'items': [
                    {
                        'dish_id': item['dish'].id,
                        'dish_name': item['dish'].name,
                        'price': str(item['price']),
                        'quantity': item['quantity'],
                    }
                    for item in cart
                ],
            }
            return redirect('payment_stub')
    else:
        form = OrderCreateForm(initial={
            'customer_name': request.user.get_full_name() or request.user.username,
        })

    return render(request, 'restaurant/checkout.html', {
        'cart': cart,
        'form': form,
    })


@login_required
def payment_stub(request):
    """Заглушка оплаты: имитация успешной / неуспешной оплаты."""
    pending = request.session.get('pending_checkout')
    cart = Cart(request)
    if not pending or len(cart) == 0:
        messages.warning(request, 'Нет заказа для оплаты')
        return redirect('cart_detail')

    if request.method == 'POST':
        action = request.POST.get('action', 'pay')
        if action == 'cancel':
            request.session.pop('pending_checkout', None)
            messages.info(request, 'Оплата отменена')
            return redirect('cart_detail')

        if action == 'fail':
            messages.error(request, 'Оплата не прошла (тестовый отказ банка). Попробуйте ещё раз.')
            return redirect('payment_stub')

        # Имитация успешной оплаты
        order = Order.objects.create(
            user=request.user,
            customer_name=pending['customer_name'],
            phone=pending['phone'],
            address=pending['address'],
            comment=pending.get('comment') or '',
            total_price=Decimal(pending['total_price']),
            status='new',
        )
        for item in pending.get('items', []):
            dish = Dish.objects.filter(pk=item['dish_id']).first()
            OrderItem.objects.create(
                order=order,
                dish=dish,
                dish_name=item['dish_name'],
                price=Decimal(item['price']),
                quantity=item['quantity'],
            )
        cart.clear()
        request.session.pop('pending_checkout', None)
        messages.success(request, 'Оплата прошла успешно (тестовый режим)')
        return redirect('order_success', order_id=order.id)

    return render(request, 'restaurant/payment.html', {
        'pending': pending,
        'total_price': pending['total_price'],
        'items': pending.get('items', []),
    })


def _user_can_view_order(user, order):
    """Пользователь видит только свой заказ (суперюзер — любой)."""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return order.user_id is not None and order.user_id == user.id


def order_success(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    if not _user_can_view_order(request.user, order):
        messages.error(request, 'Нет доступа к этому заказу')
        if request.user.is_authenticated:
            return redirect('cabinet')
        return redirect('login')
    return render(request, 'restaurant/order_success.html', {
        'order_id': order.id,
        'order': order,
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
    """Отслеживание статуса и состав — только свой заказ."""
    order = get_object_or_404(
        Order.objects.prefetch_related('items'),
        pk=order_id,
    )
    if not _user_can_view_order(request.user, order):
        messages.error(request, 'Вы можете просматривать только свои заказы')
        return redirect('cabinet')

    status_steps = [
        ('new', 'Новый'),
        ('cooking', 'Готовится'),
        ('delivery', 'Доставляется'),
        ('done', 'Выполнен'),
    ]
    current_codes = [code for code, _ in status_steps]
    try:
        current_index = current_codes.index(order.status)
    except ValueError:
        current_index = -1  # canceled или неизвестный

    return render(request, 'restaurant/order_detail.html', {
        'order': order,
        'status_steps': status_steps,
        'current_index': current_index,
        'is_canceled': order.status == 'canceled',
    })


@login_required
def order_status_poll(request, order_id):
    """JSON-статус своего заказа для автообновления."""
    order = get_object_or_404(Order, pk=order_id)
    if not _user_can_view_order(request.user, order):
        return JsonResponse({'error': 'forbidden'}, status=403)
    return JsonResponse({
        'id': order.id,
        'status': order.status,
        'status_display': order.get_status_display(),
    })


@role_required(Profile.ROLE_MODERATOR)
def moderator_orders(request):
    """Список заказов пользователей со сменой статуса."""
    status_filter = request.GET.get('status', '')
    orders = (
        Order.objects
        .select_related('user')
        .prefetch_related('items')
        .order_by('-created_at')
    )
    valid_statuses = {code for code, _ in Order.STATUS_CHOICES}
    if status_filter in valid_statuses:
        orders = orders.filter(status=status_filter)
    else:
        status_filter = ''

    return render(request, 'restaurant/moderator/orders.html', {
        'orders': orders,
        'status_choices': Order.STATUS_CHOICES,
        'status_filter': status_filter,
    })


@role_required(Profile.ROLE_MODERATOR)
def moderator_order_detail(request, order_id):
    order = get_object_or_404(
        Order.objects.prefetch_related('items').select_related('user'),
        pk=order_id,
    )
    if request.method == 'POST':
        form = OrderStatusForm(request.POST, instance=order)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                f'Статус заказа #{order.id}: {order.get_status_display()}',
            )
            return redirect('moderator_order_detail', order_id=order.id)
    else:
        form = OrderStatusForm(instance=order)

    return render(request, 'restaurant/moderator/order_detail.html', {
        'order': order,
        'form': form,
    })


@role_required(Profile.ROLE_MODERATOR)
@require_POST
def moderator_order_status(request, order_id):
    """Быстрая смена статуса со списка заказов."""
    order = get_object_or_404(Order, pk=order_id)
    form = OrderStatusForm(request.POST, instance=order)
    if form.is_valid():
        form.save()
        messages.success(
            request,
            f'Заказ #{order.id}: {order.get_status_display()}',
        )
    else:
        messages.error(request, 'Некорректный статус заказа')

    next_url = request.POST.get('next')
    if next_url and url_has_allowed_host_and_scheme(
        next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return redirect(next_url)
    return redirect('moderator_orders')


@role_required(Profile.ROLE_MODERATOR)
def dish_create(request):
    if request.method == 'POST':
        form = DishForm(request.POST, request.FILES)
        formset = RecipeItemFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            dish = form.save()
            formset.instance = dish
            formset.save()
            messages.success(request, 'Блюдо и рецептура сохранены')
            return redirect('menu')
    else:
        form = DishForm()
        formset = RecipeItemFormSet()

    return render(request, 'restaurant/moderator/dish_form.html', {
        'form': form,
        'formset': formset,
        'title': 'Добавить блюдо',
    })


@role_required(Profile.ROLE_MODERATOR)
def dish_edit(request, pk):
    dish = get_object_or_404(Dish, pk=pk)
    if request.method == 'POST':
        form = DishForm(request.POST, request.FILES, instance=dish)
        formset = RecipeItemFormSet(request.POST, instance=dish)
        if form.is_valid() and formset.is_valid():
            form.save()
            formset.save()
            messages.success(request, 'Блюдо и рецептура обновлены')
            return redirect('menu')
    else:
        form = DishForm(instance=dish)
        formset = RecipeItemFormSet(instance=dish)

    return render(request, 'restaurant/moderator/dish_form.html', {
        'form': form,
        'formset': formset,
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
                f'Ревизия «{ingredient.name}»: остаток = {form.cleaned_data["actual_quantity"]} {ingredient.get_unit_display()}',
            )
            return redirect('accountant_ingredients')
    else:
        form = RevisionForm(initial={'actual_quantity': ingredient.stock_quantity})

    return render(request, 'restaurant/accountant/revision.html', {
        'ingredient': ingredient,
        'form': form,
    })


@role_required(Profile.ROLE_ACCOUNTANT)
def accountant_purchase(request):
    """Приход товаров: после подтверждения количества плюсуются к складу."""
    if request.method == 'POST':
        formset = PurchaseLineFormSet(request.POST)
        if formset.is_valid():
            added = []
            with transaction.atomic():
                for form in formset:
                    ingredient = form.cleaned_data.get('ingredient')
                    quantity = form.cleaned_data.get('quantity')
                    if not ingredient or not quantity:
                        continue
                    StockMovement.create_purchase(
                        ingredient=ingredient,
                        quantity=quantity,
                        user=request.user,
                    )
                    added.append(
                        f'{ingredient.name} +{quantity} {ingredient.get_unit_display()}'
                    )
            messages.success(
                request,
                'Приход подтверждён. На склад добавлено: ' + '; '.join(added),
            )
            return redirect('accountant_ingredients')
    else:
        formset = PurchaseLineFormSet()

    return render(request, 'restaurant/accountant/purchase.html', {
        'formset': formset,
    })


@role_required(Profile.ROLE_ACCOUNTANT)
def accountant_movements(request):
    """Журнал движений склада — просмотр и переход к редактированию."""
    movements = (
        StockMovement.objects
        .select_related('ingredient', 'created_by')
        .order_by('-created_at')
    )
    return render(request, 'restaurant/accountant/movements.html', {
        'movements': movements,
    })


@role_required(Profile.ROLE_ACCOUNTANT)
def accountant_movement_edit(request, pk):
    """Редактирование движения: остаток склада пересчитывается автоматически."""
    movement = get_object_or_404(
        StockMovement.objects.select_related('ingredient'),
        pk=pk,
    )
    if request.method == 'POST':
        form = StockMovementEditForm(request.POST, instance=movement)
        if form.is_valid():
            with transaction.atomic():
                form.save()
            messages.success(
                request,
                f'Движение #{movement.pk} обновлено. Остаток на складе пересчитан.',
            )
            return redirect('accountant_movements')
    else:
        form = StockMovementEditForm(instance=movement)

    return render(request, 'restaurant/accountant/movement_edit.html', {
        'form': form,
        'movement': movement,
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
    """Расход ингредиентов по выполненным заказам за период."""
    form = MovementPeriodForm(request.GET or None)
    rows = []
    orders_count = 0

    if form.is_valid():
        date_from = form.cleaned_data['date_from']
        date_to = form.cleaned_data['date_to']
        order_items = (
            OrderItem.objects
            .filter(
                order__status='done',
                order__created_at__date__gte=date_from,
                order__created_at__date__lte=date_to,
                dish__isnull=False,
            )
            .select_related('dish', 'order')
            .prefetch_related('dish__recipe_items__igridients')
        )
        order_ids = set()
        totals = defaultdict(lambda: {
            'name': '',
            'unit': '',
            'quantity': Decimal('0'),
        })
        for oi in order_items:
            order_ids.add(oi.order_id)
            for ri in oi.dish.recipe_items.all():
                ing = ri.igridients
                totals[ing.pk]['name'] = ing.name
                totals[ing.pk]['unit'] = ing.get_unit_display()
                totals[ing.pk]['quantity'] += ri.quantity * oi.quantity

        rows = sorted(totals.values(), key=lambda r: r['name'].lower())
        orders_count = len(order_ids)

    return render(request, 'restaurant/accountant/consumption.html', {
        'form': form,
        'rows': rows,
        'orders_count': orders_count,
    })


@role_required(Profile.ROLE_ACCOUNTANT)
def accountant_consumption_export(request):
    form = MovementPeriodForm(request.GET or None)
    if not form.is_valid():
        messages.error(request, 'Укажите корректный период или даты')
        return redirect('accountant_consumption')

    date_from = form.cleaned_data['date_from']
    date_to = form.cleaned_data['date_to']
    order_items = (
        OrderItem.objects
        .filter(
            order__status='done',
            order__created_at__date__gte=date_from,
            order__created_at__date__lte=date_to,
            dish__isnull=False,
        )
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
            totals[ing.pk]['unit'] = ing.get_unit_display()
            totals[ing.pk]['quantity'] += ri.quantity * oi.quantity

    rows = sorted(totals.values(), key=lambda r: r['name'].lower())

    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = (
        f'attachment; filename="consumption_{date_from}_{date_to}.csv"'
    )
    writer = csv.writer(response, delimiter=';')
    writer.writerow(['Ингредиент', 'Израсходовано', 'Ед.'])
    for row in rows:
        writer.writerow([row['name'], row['quantity'], row['unit']])
    return response


@role_required(Profile.ROLE_ACCOUNTANT)
def accountant_income(request):
    """Отчёт о доходах по выполненным заказам за период."""
    form = MovementPeriodForm(request.GET or None)
    orders = []
    daily_rows = []
    dish_rows = []
    total_income = Decimal('0')
    orders_count = 0
    avg_check = Decimal('0')

    if form.is_valid():
        date_from = form.cleaned_data['date_from']
        date_to = form.cleaned_data['date_to']
        orders_qs = (
            Order.objects
            .filter(
                status='done',
                created_at__date__gte=date_from,
                created_at__date__lte=date_to,
            )
            .prefetch_related('items')
            .order_by('-created_at')
        )
        orders = list(orders_qs)
        orders_count = len(orders)
        total_income = sum((o.total_price for o in orders), Decimal('0'))
        avg_check = (
            (total_income / orders_count).quantize(Decimal('0.01'))
            if orders_count
            else Decimal('0')
        )

        daily_rows = list(
            Order.objects
            .filter(
                status='done',
                created_at__date__gte=date_from,
                created_at__date__lte=date_to,
            )
            .annotate(day=TruncDate('created_at'))
            .values('day')
            .annotate(
                orders_count=Count('id'),
                income=Sum('total_price'),
            )
            .order_by('day')
        )

        dish_totals = defaultdict(lambda: {
            'name': '',
            'quantity': 0,
            'income': Decimal('0'),
        })
        for order in orders:
            for item in order.items.all():
                key = item.dish_name
                dish_totals[key]['name'] = item.dish_name
                dish_totals[key]['quantity'] += item.quantity
                dish_totals[key]['income'] += item.price * item.quantity
        dish_rows = sorted(
            dish_totals.values(),
            key=lambda r: r['income'],
            reverse=True,
        )

    return render(request, 'restaurant/accountant/income.html', {
        'form': form,
        'orders': orders,
        'daily_rows': daily_rows,
        'dish_rows': dish_rows,
        'total_income': total_income,
        'orders_count': orders_count,
        'avg_check': avg_check,
    })


@role_required(Profile.ROLE_ACCOUNTANT)
def accountant_income_export(request):
    form = MovementPeriodForm(request.GET or None)
    if not form.is_valid():
        messages.error(request, 'Укажите корректный период дат')
        return redirect('accountant_income')

    date_from = form.cleaned_data['date_from']
    date_to = form.cleaned_data['date_to']
    orders = (
        Order.objects
        .filter(
            status='done',
            created_at__date__gte=date_from,
            created_at__date__lte=date_to,
        )
        .order_by('created_at')
    )

    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = (
        f'attachment; filename="income_{date_from}_{date_to}.csv"'
    )
    writer = csv.writer(response, delimiter=';')
    writer.writerow(['№ заказа', 'Дата', 'Клиент', 'Телефон', 'Сумма, ₽'])
    total = Decimal('0')
    for order in orders:
        writer.writerow([
            order.id,
            order.created_at.strftime('%d.%m.%Y %H:%M'),
            order.customer_name,
            order.phone,
            order.total_price,
        ])
        total += order.total_price
    writer.writerow([])
    writer.writerow(['Итого', '', '', '', total])
    return response


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


def _is_support_user(user):
    if user.is_superuser:
        return True
    profile = getattr(user, 'profile', None)
    return bool(profile and profile.is_active and profile.is_support)


def _assign_support_agent(conversation, agent):
    """Назначает оператора и уведомляет пользователя (один раз)."""
    if conversation.agent_id:
        return False
    conversation.agent = agent
    conversation.status = SupportConversation.STATUS_OPEN
    conversation.save(update_fields=['agent', 'status', 'updated_at'])
    SupportMessage.objects.create(
        conversation=conversation,
        sender=agent,
        text=f'Оператор {agent.username} подключился к чату',
        is_from_support=True,
    )
    cache.set(
        f'support_agent_joined:{conversation.user_id}',
        agent.username,
        timeout=60 * 60 * 24,
    )
    return True


def _serialize_support_message(msg):
    return {
        'id': msg.id,
        'text': msg.text,
        'is_from_support': msg.is_from_support,
        'sender': msg.sender.username,
        'created_at': msg.created_at.strftime('%d.%m.%Y %H:%M'),
        'is_join_notice': msg.text.startswith('Оператор ') and 'подключился к чату' in msg.text,
    }


@login_required
def support_chat(request):
    """Чат пользователя с поддержкой (один открытый диалог)."""
    if _is_support_user(request.user) and not request.user.is_superuser:
        return redirect('support_inbox')

    conversation = SupportConversation.get_or_open_for_user(request.user)

    if request.method == 'POST':
        form = SupportMessageForm(request.POST)
        if form.is_valid():
            SupportMessage.objects.create(
                conversation=conversation,
                sender=request.user,
                text=form.cleaned_data['text'].strip(),
                is_from_support=False,
            )
            if conversation.status == SupportConversation.STATUS_CLOSED:
                conversation.status = SupportConversation.STATUS_OPEN
            else:
                conversation.status = SupportConversation.STATUS_WAITING
            conversation.save(update_fields=['status', 'updated_at'])
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                last = conversation.messages.order_by('-created_at').first()
                return JsonResponse({'ok': True, 'message': _serialize_support_message(last)})
            return redirect('support_chat')
    else:
        form = SupportMessageForm()

    messages_qs = conversation.messages.select_related('sender')
    return render(request, 'restaurant/support/chat.html', {
        'conversation': conversation,
        'chat_messages': messages_qs,
        'form': form,
        'is_agent_view': False,
    })


@login_required
def support_chat_poll(request, pk):
    """JSON-поллинг новых сообщений (как в современных чатах)."""
    conversation = get_object_or_404(SupportConversation, pk=pk)
    is_agent = _is_support_user(request.user)
    if not is_agent and conversation.user_id != request.user.id:
        return JsonResponse({'error': 'forbidden'}, status=403)

    after_id = request.GET.get('after', '0')
    try:
        after_id = int(after_id)
    except (TypeError, ValueError):
        after_id = 0

    qs = conversation.messages.select_related('sender').filter(pk__gt=after_id)
    return JsonResponse({
        'messages': [_serialize_support_message(m) for m in qs],
        'status': conversation.status,
        'status_display': conversation.get_status_display(),
        'agent': conversation.agent.username if conversation.agent_id else None,
    })


@role_required(Profile.ROLE_SUPPORT)
def support_inbox(request):
    """Очередь чатов для операторов поддержки."""
    open_chats = (
        SupportConversation.objects
        .exclude(status=SupportConversation.STATUS_CLOSED)
        .select_related('user', 'agent')
        .prefetch_related('messages')
    )
    my_chats = open_chats.filter(agent=request.user)
    unassigned = open_chats.filter(agent__isnull=True)
    others = open_chats.exclude(agent=request.user).exclude(agent__isnull=True)
    closed = (
        SupportConversation.objects
        .filter(status=SupportConversation.STATUS_CLOSED)
        .select_related('user', 'agent')[:20]
    )
    return render(request, 'restaurant/support/inbox.html', {
        'my_chats': my_chats,
        'unassigned': unassigned,
        'others': others,
        'closed': closed,
    })


@role_required(Profile.ROLE_SUPPORT)
def support_conversation(request, pk):
    """Диалог оператора с пользователем."""
    conversation = get_object_or_404(
        SupportConversation.objects.select_related('user', 'agent'),
        pk=pk,
    )

    if request.method == 'POST':
        action = request.POST.get('action', 'send')
        if action == 'claim':
            if _assign_support_agent(conversation, request.user):
                messages.success(request, 'Вы подключились к чату. Пользователь получит уведомление.')
            else:
                messages.info(request, 'Чат уже закреплён за оператором')
            return redirect('support_conversation', pk=pk)

        if action == 'close':
            conversation.status = SupportConversation.STATUS_CLOSED
            conversation.save(update_fields=['status', 'updated_at'])
            messages.info(request, 'Чат закрыт')
            return redirect('support_inbox')

        if action == 'reopen':
            conversation.status = SupportConversation.STATUS_OPEN
            conversation.save(update_fields=['status', 'updated_at'])
            return redirect('support_conversation', pk=pk)

        form = SupportMessageForm(request.POST)
        if form.is_valid():
            _assign_support_agent(conversation, request.user)
            SupportMessage.objects.create(
                conversation=conversation,
                sender=request.user,
                text=form.cleaned_data['text'].strip(),
                is_from_support=True,
            )
            conversation.status = SupportConversation.STATUS_OPEN
            conversation.save(update_fields=['status', 'updated_at'])
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                # Отдаём оба новых сообщения после last id клиента нет — вернём последнее;
                # полл подтянет join-notice. Для AJAX отправим последнее сообщение оператора.
                last = conversation.messages.order_by('-created_at').first()
                return JsonResponse({'ok': True, 'message': _serialize_support_message(last)})
            return redirect('support_conversation', pk=pk)
    else:
        form = SupportMessageForm()

    user_orders = (
        Order.objects
        .filter(user=conversation.user)
        .prefetch_related('items')
        .order_by('-created_at')[:30]
    )

    return render(request, 'restaurant/support/chat.html', {
        'conversation': conversation,
        'chat_messages': conversation.messages.select_related('sender'),
        'form': form,
        'is_agent_view': True,
        'user_orders': user_orders,
    })
