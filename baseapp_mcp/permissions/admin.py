from django.contrib import admin
from django.contrib.auth.models import Permission


@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    search_fields = ("name", "codename", "content_type__app_label")
    list_display = ("name", "codename", "content_type__app_label")
