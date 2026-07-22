from django.urls import path
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
]