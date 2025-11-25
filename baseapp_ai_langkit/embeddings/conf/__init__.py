import typing

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

T = typing.TypeVar("T")


class AppSettings:
    EMBEDDING_MODEL_DIMENSIONS: int
    CHUNK_SIZE: int
    CHUNK_OVERLAP: int
    SKIP_EMBEDDING_GENERATION: bool

    def __init__(self, prefix):
        self.prefix = prefix
        self.EMBEDDING_MODEL_DIMENSIONS = self._get_setting(
            name="EMBEDDING_MODEL_DIMENSIONS", expected_type=int
        )
        self.CHUNK_SIZE = self._get_setting(name="CHUNK_SIZE", expected_type=int, default=512)
        self.CHUNK_OVERLAP = self._get_setting(name="CHUNK_OVERLAP", expected_type=int, default=64)
        self.SKIP_EMBEDDING_GENERATION = self._get_setting(
            name="SKIP_EMBEDDING_GENERATION", expected_type=bool, default=False
        )

    def _get_setting(self, name: str, expected_type: T, default: typing.Any = None) -> T:
        path = "_".join([self.prefix, name])
        value = getattr(settings, path, default)
        if not isinstance(value, expected_type):
            raise ImproperlyConfigured(f"Expected type:{expected_type} for settings.{path}")
        return value


app_settings = AppSettings(prefix="BASEAPP_AI_LANGKIT_EMBEDDINGS")
