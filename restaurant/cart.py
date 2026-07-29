from decimal import Decimal
from .models import Dish


class Cart:
    def __init__(self, request):
        self.session = request.session
        cart = self.session.get('cart')
        if not cart:
            cart = self.session['cart'] = {}
        cleaned = {}
        for dish_id, data in cart.items():
            if not isinstance(data, dict):
                continue
            quantity = data.get('quantity', 0)
            try:
                quantity = int(quantity)
            except (TypeError, ValueError):
                continue
            if quantity > 0:
                cleaned[str(dish_id)] = {'quantity': quantity}
        if cleaned != cart:
            self.session['cart'] = cleaned
            self.session.modified = True
        self.cart = self.session['cart']

    def add(self, dish_id, quantity=1):
        dish_id = str(dish_id)
        if dish_id not in self.cart:
            self.cart[dish_id] = {'quantity': 0}
        self.cart[dish_id]['quantity'] += quantity
        self.save()

    def remove(self, dish_id):
        dish_id = str(dish_id)
        if dish_id in self.cart:
            del self.cart[dish_id]
            self.save()

    def update(self, dish_id, quantity):
        dish_id = str(dish_id)
        if dish_id in self.cart:
            if quantity > 0:
                self.cart[dish_id]['quantity'] = quantity
            else:
                self.remove(dish_id)
            self.save()

    def clear(self):
        self.session['cart'] = {}
        self.session.modified = True

    def save(self):
        self.session['cart'] = self.cart
        self.session.modified = True

    def __iter__(self):
        dish_ids = list(self.cart.keys())
        dishes = Dish.objects.filter(id__in=dish_ids, is_available=True)
        for dish in dishes:
            # Копия, чтобы не записывать Dish в session['cart']
            raw = self.cart.get(str(dish.id))
            if not raw:
                continue
            item = dict(raw)
            item['dish'] = dish
            item['price'] = dish.price
            item['total'] = dish.price * item['quantity']
            yield item

    def __len__(self):
        return sum(item['quantity'] for item in self.cart.values())
        
    def get_total_price(self):
        return sum(
            (item['dish'].price * item['quantity'] for item in self),
            Decimal('0'),
        )