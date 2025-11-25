from django.contrib import admin

from baseapp_ai_langkit.embeddings.admin import EmbeddableModelAdminMixin

from .models import ExampleEmbeddable, ExampleHTMLEmbeddable


@admin.register(ExampleEmbeddable)
class ExampleEmbeddableAdmin(EmbeddableModelAdminMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "created",
        "modified",
        "embedding_error",
    )
    search_fields = ["text"]
    readonly_fields = ["embedding_error"]

    actions = [*EmbeddableModelAdminMixin.actions]


@admin.register(ExampleHTMLEmbeddable)
class ExampleHTMLEmbeddableAdmin(EmbeddableModelAdminMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "created",
        "modified",
        "embedding_error",
    )
    search_fields = ["html"]
    readonly_fields = ["embedding_error"]

    actions = [*EmbeddableModelAdminMixin.actions]
