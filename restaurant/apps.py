from django.apps import AppConfig


class RestaurantConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'restaurant'

    def ready(self):
        # Импорт сигналов из models (create_profile)
        from . import models  # noqa: F401
