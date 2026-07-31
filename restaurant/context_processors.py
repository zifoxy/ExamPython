from django.core.cache import cache
from django.core.exceptions import ObjectDoesNotExist

from .cart import Cart
from .models import SupportConversation


def cart(request):
    cart_obj = Cart(request)
    context = {'cart_count': len(cart_obj)}

    user_profile = None
    is_moderator = False
    is_accountant = False
    is_support = False
    support_unread = 0
    support_join_notice = None
    if request.user.is_authenticated:
        try:
            user_profile = request.user.profile
            is_moderator = (
                request.user.is_superuser
                or (user_profile.is_active and user_profile.role == 'moderator')
            )
            is_accountant = (
                request.user.is_superuser
                or (user_profile.is_active and user_profile.role == 'accountant')
            )
            is_support = (
                request.user.is_superuser
                or (user_profile.is_active and user_profile.role == 'support')
            )
            if is_support:
                support_unread = (
                    SupportConversation.objects
                    .exclude(status=SupportConversation.STATUS_CLOSED)
                    .filter(agent__isnull=True)
                    .count()
                )
            else:
                agent_name = cache.get(f'support_agent_joined:{request.user.id}')
                if agent_name:
                    support_join_notice = agent_name
                    cache.delete(f'support_agent_joined:{request.user.id}')
        except ObjectDoesNotExist:
            user_profile = None

    context['user_profile'] = user_profile
    context['is_moderator'] = is_moderator
    context['is_accountant'] = is_accountant
    context['is_support'] = is_support
    context['support_unread'] = support_unread
    context['support_join_notice'] = support_join_notice
    return context
