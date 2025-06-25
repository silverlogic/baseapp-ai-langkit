from django.contrib import admin

from baseapp_ai_langkit.base.utils.model_admin_helper import ModelAdmin, TabularInline

from .models import DefaultDocumentEmbedding, DefaultVectorStore, DefaultVectorStoreTool


class DefaultDocumentEmbeddingInline(TabularInline):
    model = DefaultDocumentEmbedding
    extra = 0
    can_delete = False
    readonly_fields = ("embedding", "content", "metadata", "created", "modified")

    def has_add_permission(self, request, obj=None):
        return False


class DefaultVectorStoreToolInline(TabularInline):
    model = DefaultVectorStoreTool
    extra = 0
    can_delete = False
    readonly_fields = ("name", "description", "created", "modified")

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(DefaultVectorStore)
class DefaultVectorStoreAdmin(ModelAdmin):
    list_display = ("name", "description", "created", "modified")
    search_fields = ("name", "description")
    ordering = ("name",)
    inlines = [DefaultVectorStoreToolInline, DefaultDocumentEmbeddingInline]


@admin.register(DefaultVectorStoreTool)
class DefaultVectorStoreToolAdmin(ModelAdmin):
    list_display = ("name", "description", "vector_store", "created", "modified")
    search_fields = ("name", "description")
    list_filter = ("vector_store",)
    ordering = ("name",)
