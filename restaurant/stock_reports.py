from decimal import Decimal

from django.db.models import Sum

from .models import Igridients, StockMovement


def build_revision_blank_rows(date_from, date_to):
    rows = []
    for ing in Igridients.objects.all():
        qs = StockMovement.objects.filter(
            ingredient=ing,
            created_at__date__gte=date_from,
            created_at__date__lte=date_to,
        )
        plus = qs.filter(quantity__gt=0).aggregate(s=Sum('quantity'))['s'] or Decimal('0')
        minus = qs.filter(quantity__lt=0).aggregate(s=Sum('quantity'))['s'] or Decimal('0')

        after = (
            StockMovement.objects.filter(
                ingredient=ing,
                created_at__date__gt=date_to,
            ).aggregate(s=Sum('quantity'))['s']
            or Decimal('0')
        )
        stock_end = ing.stock_quantity - after
        stock_start = stock_end - plus - minus

        rows.append({
            'name': ing.name,
            'unit': ing.unit,
            'stock_start': stock_start,
            'plus': plus,
            'minus': abs(minus),
            'stock_end': stock_end,
        })
    return rows
