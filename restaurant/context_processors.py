from django.core.exceptions import ObjectDoesNotExist

from .cart import Cart


def cart(request):
    cart_obj = Cart(request)
    context = {'cart_count': len(cart_obj)}

    user_profile = None
    is_moderator = False
    if request.user.is_authenticated:
        try:
            user_profile = request.user.profile
            is_moderator = (
                request.user.is_superuser
                or (user_profile.is_active and user_profile.role == 'moderator')
            )
        except ObjectDoesNotExist:
            user_profile = None

    context['user_profile'] = user_profile
    context['is_moderator'] = is_moderator
    return context
