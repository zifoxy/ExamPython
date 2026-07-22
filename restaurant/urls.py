from django.urls import path
from django.contrib.auth import views as auth_views

from . import views

urlpatterns = [
    path('', views.menu, name='menu'),
    path('dish/<int:pk>/', views.dish_detail, name='dish_detail'),
    path('cart/', views.cart_detail, name='cart_detail'),
    path('cart/add/<int:dish_id>/', views.cart_add, name='cart_add'),
    path('cart/remove/<int:dish_id>/', views.cart_remove, name='cart_remove'),
    path('cart/update/<int:dish_id>/', views.cart_update, name='cart_update'),
    path('checkout/', views.order_create, name='order_create'),
    path('order/success/<int:order_id>/', views.order_success, name='order_success'),

    # Auth
    path('register/', views.register, name='register'),
    path(
        'login/',
        auth_views.LoginView.as_view(template_name='restaurant/login.html'),
        name='login',
    ),
    path(
        'logout/',
        auth_views.LogoutView.as_view(),
        name='logout',
    ),
    path('cabinet/', views.cabinet, name='cabinet'),

    # Модератор
    path('moderator/dishes/add/', views.dish_create, name='dish_create'),
    path('moderator/dishes/<int:pk>/edit/', views.dish_edit, name='dish_edit'),
    path('moderator/dishes/<int:pk>/delete/', views.dish_delete, name='dish_delete'),
]
