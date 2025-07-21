from django.contrib import admin

from baseapp_ai_langkit.embeddings.admin import EmbeddableModelAdminMixin

from .models import ExampleEmbeddable


@admin.register(ExampleEmbeddable)
class SlackMessageAdmin(EmbeddableModelAdminMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "created",
        "modified",
        "embedding_error",
    )
    search_fields = ["text"]
    readonly_fields = ["embedding_error"]

    actions = [*EmbeddableModelAdminMixin.actions]
