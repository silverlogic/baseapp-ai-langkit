from django.apps import AppConfig
from django.db.models.signals import post_migrate
from django.utils.module_loading import autodiscover_modules


class BaseappAILangkitRunnersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "baseapp_ai_langkit.runners"
    label = "baseapp_ai_langkit_runners"

    def ready(self):
        autodiscover_modules("runners")
        from baseapp_ai_langkit.runners import checks  # noqa: F401
        from baseapp_ai_langkit.runners import model_initializers  # noqa: F401

        post_migrate.connect(self.sync_registry, sender=self)

    def sync_registry(self, **kwargs):
        from django.db import OperationalError, ProgrammingError

        from .models import LLMRunner

        try:
            LLMRunner.sync_runners()
        except (OperationalError, ProgrammingError):
            # This is expected to happen when the LLMRunner table does not exist yet.
            pass
