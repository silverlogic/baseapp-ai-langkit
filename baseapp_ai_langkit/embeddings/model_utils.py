import typing
from functools import reduce
from inspect import isclass

from django.db.models import Q


def validate_content_type_for_model(model_cls: typing.Type):
    from baseapp_ai_langkit.embeddings.models import EmbeddableModelMixin

    if isclass(model_cls) is False:
        raise Exception(f"{model_cls} must be a class")
    if issubclass(model_cls, EmbeddableModelMixin) is False:
        raise Exception(f"{model_cls.__name__} must extend {EmbeddableModelMixin.__name__}")


def available_content_types_query() -> Q:
    """
    Returns a Q instance to fetch ContentTypes that extend GenericEmbeddableModelChunk
    Example Usage:
        ContentType.objects.all().filter(
            available_content_types_query()
        )
    """
    from baseapp_ai_langkit.embeddings.models import EmbeddableModelMixin

    return reduce(
        lambda q, x: q | Q(app_label=x._meta.app_label, model=x._meta.model_name),
        EmbeddableModelMixin.__subclasses__(),
        Q(),
    )
