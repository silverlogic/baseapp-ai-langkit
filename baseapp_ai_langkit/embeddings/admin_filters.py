from django.contrib import admin


class ContentTypeFilter(admin.SimpleListFilter):
    title = "Content Type"
    parameter_name = "content_type"

    def lookups(self, request, model_admin):
        queryset = model_admin.get_queryset(request)
        types = queryset.values_list("content_type_id", "content_type__model")
        return list(types.order_by("content_type__model").distinct())

    def queryset(self, request, queryset):
        if value := self.value():
            queryset = queryset.filter(content_type_id=value)
        return queryset
