from functools import wraps
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from .models import Profile, Dish
from django.shortcuts import get_object_or_404
from .forms import DishForm
from django.contrib import messages
from django.shortcuts import redirect, render


def role_required(*roles):
    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            profile = getattr(request.user, 'profile', None)
            if profile is None or profile.role not in roles:
                if not request.user.is_superuser:
                    raise PermissionDenied
            return view_func(request, *args, **kwargs)
        return _wrapped
    return decorator

@role_required(Profile.ROLE_MODERATOR)
def dish_edit(request, pk):
    dish = get_object_or_404(Dish, pk=pk)
    if request.method == 'POST':
        form = DishForm(request.POST, request.FILES, instance=dish)
        if form.is_valid():
            form.save()
            messages.success(request, 'Блюдо успешно обновлено')
            return redirect('menu')

    else:
        form = DishForm(instance=dish)

    return render(request, 'restaurant/moderator/dish_form.html', {
        'form': form,
        'title': 'Редактировать блюдо',
    })