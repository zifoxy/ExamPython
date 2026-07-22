from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.contrib import messages
from .models import Category, Dish, OrderItem, Profile
from .cart import Cart
from .forms import OrderCreateForm, DishForm
from .decorators import role_required


def menu(request):
    categories = Category.objects.prefetch_related('dishes').all()
    cart = Cart(request)
    return render(request, 'restaurant/menu.html', {
        'categories': categories,
        'cart_count': len(cart),
    })

def dish_detail(request, pk):
    dish = get_object_or_404(Dish, pk=pk, is_available=True)
    return render(request, 'restaurant/dish_detail.html', {'dish': dish})

@require_POST
def cart_add(request, dish_id):
    cart = Cart(request)
    dish = get_object_or_404(Dish, id=dish_id, is_available=True)
    quantity = int(request.POST.get('quantity', 1))
    cart.add(dish.id, quantity)
    messages.success(request, f'«{dish.name}» добавлено в корзину')
    return redirect(request.POST.get('next') or 'menu')

@require_POST
def cart_remove(request, dish_id):
    cart = Cart(request)
    cart.remove(dish_id)
    return redirect('cart_detail')

@require_POST
def cart_update(request, dish_id):
    cart = Cart(request)
    quantity = int(request.POST.get('quantity', 1))
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
    return render(request, 'restaurant/order_success.html', {
        'order_id': order_id,
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