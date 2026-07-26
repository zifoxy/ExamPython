from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver


class Profile(models.Model):
    ROLE_USER = 'user'
    ROLE_MODERATOR = 'moderator'
    ROLE_ACCOUNTANT = 'accountant'
    ROLE_SUPPORT = 'support'

    ROLE_CHOICES = [
        (ROLE_USER, 'Пользователь'),
        (ROLE_MODERATOR, 'Модератор'),
        (ROLE_ACCOUNTANT, 'Бухгалтер'),
        (ROLE_SUPPORT, 'Поддержка'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile', verbose_name='Пользователь')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=ROLE_USER, verbose_name='Роль')
    is_active = models.BooleanField(default=True, verbose_name='Активен')

    class Meta:
        verbose_name = 'Профиль'
        verbose_name_plural = 'Профили'

    def __str__(self):
        return f'{self.user.username} ({self.get_role_display()})'

    @property
    def is_moderator(self):
        return self.role == self.ROLE_MODERATOR

    @property
    def is_accountant(self):
        return self.role == self.ROLE_ACCOUNTANT
    
    @property
    def is_support(self): 
        return self.role == self.ROLE_SUPPORT

@receiver(post_save, sender=User)
def create_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

class Category(models.Model):
    name = models.CharField(max_length=100, verbose_name='Название')
    slug = models.SlugField(unique=True)

    class Meta: 
        verbose_name = 'Категория'
        verbose_name_plural = 'Категории'
        ordering = ['name']

    def __str__(self):
        return self.name

class Dish(models.Model):
    category = models.ForeignKey(Category, on_delete=models.CASCADE, verbose_name='Категория', related_name='dishes')
    name = models.CharField(max_length=200, verbose_name='Название')
    description = models.TextField(verbose_name='Описание')
    price = models.DecimalField(max_digits=8, decimal_places=2, verbose_name='Цена')
    image = models.ImageField('Фото', upload_to='dishes/', blank=True, null=True)
    is_available = models.BooleanField('В наличии', default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Блюдо'
        verbose_name_plural = 'Блюда'
        ordering = ['name']

    def __str__(self):
        return f'{self.name} - {self.price}'

class Order(models.Model):
    STATUS_CHOICES = [
        ('new', 'Новый'),
        ('cooking', 'Готовится'),
        ('delivery', 'Доставляется'),
        ('done', 'Выполнен'),
        ('canceled', 'Отменен'),
    ]

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='orders', verbose_name='Пользователь')
    customer_name = models.CharField(max_length=100, verbose_name='Имя клиента')
    phone = models.CharField(max_length=15, verbose_name='Телефон')
    address = models.CharField(max_length=200, verbose_name='Адрес Доставки')
    comment = models.TextField(verbose_name='Комментарий', blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new', verbose_name='Статус')
    total_price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Общая стоимость', default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta: 
        verbose_name = 'Заказ'
        verbose_name_plural = 'Заказы'
        ordering = ['-created_at']

    def __str__(self):
        return f'Заказ №{self.id} - {self.customer_name}'

class OrderItem(models.Model):
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='items',
        verbose_name='Заказ',
    )
    dish = models.ForeignKey(
        Dish,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name='Блюдо',
    )
    dish_name = models.CharField('Название блюда', max_length=200)
    price = models.DecimalField('Цена', max_digits=8, decimal_places=2)
    quantity = models.PositiveIntegerField('Количество', default=1)
    class Meta:
        verbose_name = 'Позиция заказа'
        verbose_name_plural = 'Позиции заказа'
    def __str__(self):
        return f'{self.dish_name} x{self.quantity}'
    @property
    def subtotal(self):
        return self.price * self.quantity

class Igridients(models.Model):
    UNIT_G = 'g'
    UNIT_PCS = 'pcs'
    UNIT_ML = 'ml'

    UNIT_CHOICES = [
        (UNIT_G, 'грамм'),
        (UNIT_PCS, 'штук'),
        (UNIT_ML, 'миллилитров'),
    ]

    name = models.CharField(max_length=100, verbose_name='Название')
    unit = models.CharField(
        max_length=10,
        choices=UNIT_CHOICES,
        default=UNIT_G,
        verbose_name='Единица измерения',
    )
    stock_quantity = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Количество на складе')

    class Meta:
        verbose_name = 'Ингредиент'
        verbose_name_plural = 'Ингредиенты'
        ordering = ['name']

    def __str__(self):
        return self.name

class RecipeItem(models.Model):
    dish = models.ForeignKey(Dish, on_delete=models.CASCADE, verbose_name='Блюдо', related_name='recipe_items')
    igridients = models.ForeignKey(Igridients, on_delete=models.CASCADE, verbose_name='Ингредиент', related_name='recipe_items')
    quantity = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Количество на блюдо')

    class Meta:
        verbose_name = 'Рецепт'
        verbose_name_plural = 'Рецепты'
        ordering = ['dish']
        unique_together = ('dish', 'igridients')

    def __str__(self):
        return f'{self.dish.name} - {self.igridients.name} - {self.quantity}'


class StockMovement(models.Model):
    """Движение склада. quantity: + приход, − списание. Остаток синхронизируется при create/update/delete."""

    REASON_PURCHASE = 'purchase'
    REASON_REVISION = 'revision'
    REASON_WRITE_OFF = 'write_off'
    REASON_SALE = 'sale'

    REASON_CHOICES = [
        (REASON_PURCHASE, 'Приход'),
        (REASON_REVISION, 'Ревизия'),
        (REASON_WRITE_OFF, 'Списание'),
        (REASON_SALE, 'Продажа'),
    ]

    ingredient = models.ForeignKey(
        Igridients,
        on_delete=models.CASCADE,
        related_name='movements',
        verbose_name='Ингредиент',
    )
    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name='Изменение (+/−)',
        help_text='Положительное — приход, отрицательное — списание',
    )
    reason = models.CharField(
        max_length=20,
        choices=REASON_CHOICES,
        verbose_name='Причина',
    )
    note = models.CharField(max_length=255, blank=True, verbose_name='Комментарий')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата')
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='stock_movements',
        verbose_name='Кто создал',
    )

    class Meta:
        verbose_name = 'Движение склада'
        verbose_name_plural = 'Движения склада'
        ordering = ['-created_at']

    def __str__(self):
        sign = '+' if self.quantity >= 0 else ''
        return f'{self.ingredient.name}: {sign}{self.quantity} ({self.get_reason_display()})'

    def save(self, *args, **kwargs):
        """
        Создание: остаток += quantity.
        Редактирование: сначала откат старого влияния, затем применение нового.
        """
        from django.db import transaction

        with transaction.atomic():
            if self.pk is None:
                super().save(*args, **kwargs)
                Igridients.objects.filter(pk=self.ingredient_id).update(
                    stock_quantity=models.F('stock_quantity') + self.quantity,
                )
                return

            old = (
                StockMovement.objects
                .select_for_update()
                .get(pk=self.pk)
            )
            Igridients.objects.filter(pk=old.ingredient_id).update(
                stock_quantity=models.F('stock_quantity') - old.quantity,
            )
            super().save(*args, **kwargs)
            Igridients.objects.filter(pk=self.ingredient_id).update(
                stock_quantity=models.F('stock_quantity') + self.quantity,
            )

    def delete(self, *args, **kwargs):
        """При удалении откатываем влияние на остаток склада."""
        from django.db import transaction

        with transaction.atomic():
            Igridients.objects.filter(pk=self.ingredient_id).update(
                stock_quantity=models.F('stock_quantity') - self.quantity,
            )
            super().delete(*args, **kwargs)

    @classmethod
    def create_purchase(cls, ingredient, quantity, user=None, note=''):
        """Приход товара: quantity > 0 плюсуется к складу."""
        from decimal import Decimal

        qty = Decimal(quantity)
        if qty <= 0:
            raise ValueError('Количество прихода должно быть больше нуля')
        return cls.objects.create(
            ingredient=ingredient,
            quantity=qty,
            reason=cls.REASON_PURCHASE,
            created_by=user,
            note=note or 'Приход товаров',
        )

    @classmethod
    def create_revision(cls, ingredient, actual_quantity, user=None, note=''):
        """
        Бухгалтер вводит факт на полке.
        В историю пишется разница: факт − учёт.
        После save() остаток станет равным actual_quantity.
        """
        from decimal import Decimal
        from django.db import transaction

        actual = Decimal(actual_quantity)
        with transaction.atomic():
            locked = Igridients.objects.select_for_update().get(pk=ingredient.pk)
            current = locked.stock_quantity
            delta = actual - current
            return cls.objects.create(
                ingredient=locked,
                quantity=delta,
                reason=cls.REASON_REVISION,
                created_by=user,
                note=note or f'Ревизия: учёт {current} → факт {actual}',
            )
