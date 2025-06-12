from django.contrib import admin


class ChannelTypeFilter(admin.SimpleListFilter):
    title = "Channel Type"
    parameter_name = "channel_type"

    def lookups(self, request, model_admin):
        return (
            ("dm", "Direct Message"),
            ("channel", "Channel"),
        )

    def queryset(self, request, queryset):
        if self.value() == "dm":
            return queryset.filter(output_response_output_data__channel__startswith="D")
        elif self.value() == "channel":
            return queryset.filter(output_response_output_data__channel__startswith="C")
        return queryset
