from decimal import Decimal

from django import forms
from django.forms import inlineformset_factory
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Order, Dish, RecipeItem, Igridients, StockMovement


class OrderCreateForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ('customer_name', 'phone', 'address', 'comment')
        widgets = {
            'customer_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ваше имя',
            }),
            'phone': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '+7 (999) 123-45-67',
            }),
            'address': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Улица, дом, квартира',
            }),
            'comment': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,

                'placeholder': 'Код домофона, этаж...',
            }),
        }


class OrderStatusForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ('status',)
        widgets = {
            'status': forms.Select(attrs={'class': 'form-select form-select-sm'}),
        }


class IngredientChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return f'{obj.name} ({obj.get_unit_display()})'


class IngredientSelect(forms.Select):
    """Select с data-unit у каждой опции — для подписи рядом с количеством."""

    def __init__(self, *args, unit_map=None, **kwargs):
        self.unit_map = unit_map or {}
        super().__init__(*args, **kwargs)

    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex=subindex, attrs=attrs)
        if value:
            pk = str(getattr(value, 'value', value))
            unit = self.unit_map.get(pk)
            if unit:
                option['attrs']['data-unit'] = unit
        return option


class DishForm(forms.ModelForm):
    class Meta:
        model = Dish
        fields = ('category', 'name', 'description', 'price', 'image', 'is_available')
        widgets = {
            'category': forms.Select(attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'image': forms.ClearableFileInput(attrs={'class': 'form-control'}),
            'is_available': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class RecipeItemForm(forms.ModelForm):
    igridients = IngredientChoiceField(
        queryset=Igridients.objects.all(),
        label='Ингредиент',
        widget=IngredientSelect(attrs={
            'class': 'form-select form-select-sm ingredient-select',
        }),
    )

    class Meta:
        model = RecipeItem
        fields = ('igridients', 'quantity')
        labels = {
            'quantity': 'Количество',
        }
        widgets = {
            'quantity': forms.NumberInput(attrs={
                'class': 'form-control form-control-sm',
                'step': '0.01',
                'min': '0.01',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        unit_map = {
            str(ing.pk): ing.get_unit_display()
            for ing in Igridients.objects.all()
        }
        self.fields['igridients'].widget.unit_map = unit_map
        self.fields['igridients'].queryset = Igridients.objects.all()


RecipeItemFormSet = inlineformset_factory(
    Dish,
    RecipeItem,
    form=RecipeItemForm,
    extra=3,
    can_delete=True,
)


class RegisterForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control'}),
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'password1', 'password2')
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs.update({'class': 'form-control'})
        self.fields['password2'].widget.attrs.update({'class': 'form-control'})


class RevisionForm(forms.Form):
    actual_quantity = forms.DecimalField(
        label='Факт на полке',
        min_value=Decimal('0'),
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'min': '0',
        }),
    )
    note = forms.CharField(
        label='Комментарий',
        required=False,
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Необязательно',
        }),
    )


class MovementPeriodForm(forms.Form):
    date_from = forms.DateField(
        label='С',
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control',
        }),
    )
    date_to = forms.DateField(
        label='По',
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control',
        }),
    )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('date_from') and cleaned.get('date_to'):
            if cleaned['date_from'] > cleaned['date_to']:
                raise forms.ValidationError('Дата начала не может быть позже даты окончания')
        return cleaned


class PurchaseLineForm(forms.Form):
    ingredient = IngredientChoiceField(
        queryset=Igridients.objects.all(),
        label='Ингредиент',
        required=False,
        widget=IngredientSelect(attrs={'class': 'form-select'}),
    )
    quantity = forms.DecimalField(
        label='Количество',
        required=False,
        min_value=Decimal('0.01'),
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'min': '0.01',
            'placeholder': '0',
        }),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        unit_map = {
            str(ing.pk): ing.get_unit_display()
            for ing in Igridients.objects.all()
        }
        self.fields['ingredient'].widget.unit_map = unit_map
        self.fields['ingredient'].queryset = Igridients.objects.all()

    def clean(self):
        cleaned = super().clean()
        ingredient = cleaned.get('ingredient')
        quantity = cleaned.get('quantity')
        if ingredient and not quantity:
            self.add_error('quantity', 'Укажите количество')
        if quantity and not ingredient:
            self.add_error('ingredient', 'Выберите ингредиент')
        return cleaned


class PurchaseFormSet(forms.BaseFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        filled = [
            form
            for form in self.forms
            if form.cleaned_data.get('ingredient') and form.cleaned_data.get('quantity')
        ]
        if not filled:
            raise forms.ValidationError('Добавьте хотя бы одну позицию прихода')


PurchaseLineFormSet = forms.formset_factory(
    PurchaseLineForm,
    formset=PurchaseFormSet,
    extra=5,
)


class StockMovementEditForm(forms.ModelForm):
    ingredient = IngredientChoiceField(
        queryset=Igridients.objects.all(),
        label='Ингредиент',
        widget=IngredientSelect(attrs={'class': 'form-select'}),
    )

    class Meta:
        model = StockMovement
        fields = ('ingredient', 'quantity', 'reason', 'note')
        labels = {
            'quantity': 'Изменение (+/−)',
            'reason': 'Причина',
            'note': 'Комментарий',
        }
        help_texts = {
            'quantity': 'Положительное — приход, отрицательное — списание со склада',
        }
        widgets = {
            'quantity': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
            }),
            'reason': forms.Select(attrs={'class': 'form-select'}),
            'note': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Необязательно',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        unit_map = {
            str(ing.pk): ing.get_unit_display()
            for ing in Igridients.objects.all()
        }
        self.fields['ingredient'].widget.unit_map = unit_map
        self.fields['ingredient'].queryset = Igridients.objects.all()

    def clean_quantity(self):
        quantity = self.cleaned_data['quantity']
        if quantity == 0:
            raise forms.ValidationError('Изменение не может быть нулевым')
        return quantity

    def clean(self):
        cleaned = super().clean()
        reason = cleaned.get('reason')
        quantity = cleaned.get('quantity')
        if reason and quantity is not None:
            if reason == StockMovement.REASON_PURCHASE and quantity < 0:
                self.add_error('quantity', 'Для прихода укажите положительное количество')
            if reason in (StockMovement.REASON_WRITE_OFF, StockMovement.REASON_SALE) and quantity > 0:
                self.add_error(
                    'quantity',
                    'Для списания/продажи укажите отрицательное количество',
                )
        return cleaned


class SupportMessageForm(forms.Form):
    text = forms.CharField(
        label='Сообщение',
        max_length=2000,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Напишите сообщение…',
            'id': 'support-message-input',
        }),
    )

