from decimal import Decimal
from .models import Dish


class Cart:
    def __init__(self, request):
        self.session = request.session
        cart = self.session.get('cart')
        if not cart:
            cart = self.session['cart'] = {}
        self.cart = cart

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
        dish_ids = self.cart.keys()
        dishes = Dish.objects.filter(id__in=dish_ids, is_available=True)
        cart = self.cart.copy()
        for dish in dishes:
            item = cart[str(dish.id)]
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