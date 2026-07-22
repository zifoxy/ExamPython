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