from django.apps import AppConfig

class RecommendationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.recommendations'

    def ready(self):
        import apps.recommendations.signals  