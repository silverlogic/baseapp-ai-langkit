from django.contrib import admin

from ..tools.admin import DefaultToolInline
from .models import DefaultDocumentEmbedding, DefaultVectorStore


class DefaultDocumentEmbeddingInline(admin.TabularInline):
    model = DefaultDocumentEmbedding
    extra = 0
    can_delete = False
    readonly_fields = ("embedding", "content", "metadata", "created", "modified")

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(DefaultVectorStore)
class DefaultVectorStoreAdmin(admin.ModelAdmin):
    list_display = ("name", "description", "created", "modified")
    search_fields = ("name", "description")
    ordering = ("name",)
    inlines = [DefaultToolInline, DefaultDocumentEmbeddingInline]
