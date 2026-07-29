from django.urls import path
from django.contrib.auth import views as auth_views

from . import views

urlpatterns = [
    path('', views.menu, name='menu'),
    path('terms-of-use/', views.terms_of_use, name='terms_of_use'),
    path('dish/<int:pk>/', views.dish_detail, name='dish_detail'),
    path('cart/', views.cart_detail, name='cart_detail'),
    path('cart/add/<int:dish_id>/', views.cart_add, name='cart_add'),
    path('cart/remove/<int:dish_id>/', views.cart_remove, name='cart_remove'),
    path('cart/update/<int:dish_id>/', views.cart_update, name='cart_update'),
    path('checkout/', views.order_create, name='order_create'),
    path('checkout/payment/', views.payment_stub, name='payment_stub'),
    path('order/success/<int:order_id>/', views.order_success, name='order_success'),

    # Auth
    path('register/', views.register, name='register'),
    path('login/', auth_views.LoginView.as_view(template_name='restaurant/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('cabinet/', views.cabinet, name='cabinet'),
    path('cabinet/orders/<int:order_id>/', views.order_detail, name='order_detail'),
    path('cabinet/orders/<int:order_id>/status/', views.order_status_poll, name='order_status_poll'),

    # Поддержка
    path('support/chat/', views.support_chat, name='support_chat'),
    path('support/chat/<int:pk>/poll/', views.support_chat_poll, name='support_chat_poll'),
    path('support/inbox/', views.support_inbox, name='support_inbox'),
    path('support/inbox/<int:pk>/', views.support_conversation, name='support_conversation'),

    # Модератор
    path('moderator/orders/', views.moderator_orders, name='moderator_orders'),
    path('moderator/orders/<int:order_id>/', views.moderator_order_detail, name='moderator_order_detail'),
    path('moderator/orders/<int:order_id>/status/', views.moderator_order_status, name='moderator_order_status'),
    path('moderator/dishes/add/', views.dish_create, name='dish_create'),
    path('moderator/dishes/<int:pk>/edit/', views.dish_edit, name='dish_edit'),
    path('moderator/dishes/<int:pk>/delete/', views.dish_delete, name='dish_delete'),

    # Бухгалтер
    path('accountant/ingredients/', views.accountant_ingredients, name='accountant_ingredients'),
    path('accountant/ingredients/<int:pk>/revision/', views.accountant_revision, name='accountant_revision'),
    path('accountant/purchase/', views.accountant_purchase, name='accountant_purchase'),
    path('accountant/movements/', views.accountant_movements, name='accountant_movements'),
    path('accountant/movements/<int:pk>/edit/', views.accountant_movement_edit, name='accountant_movement_edit'),
    path('accountant/dishes/<int:pk>/recipe/', views.accountant_recipe, name='accountant_recipe'),
    path('accountant/report/consumption/', views.accountant_consumption, name='accountant_consumption'),
    path('accountant/report/revision-blank/', views.accountant_revision_blank, name='accountant_revision_blank'),
    path('accountant/report/revision-blank/export/', views.accountant_revision_blank_export, name='accountant_revision_blank_export'),
]
