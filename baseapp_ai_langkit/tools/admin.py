from django.contrib import admin

from .models import DefaultTool


@admin.register(DefaultTool)
class DefaultToolAdmin(admin.ModelAdmin):
    list_display = ("name", "description", "vector_store", "created", "modified")
    search_fields = ("name", "description")
    list_filter = ("vector_store",)
    ordering = ("name",)


class DefaultToolInline(admin.TabularInline):
    model = DefaultTool
    extra = 0
    can_delete = False
    readonly_fields = ("name", "description", "created", "modified")

    def has_add_permission(self, request, obj=None):
        return False
