from django.apps import AppConfig

class MutualSystemConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'mutual_system'

    def ready(self):
        import mutual_system.signals  # noqa