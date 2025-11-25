import json
import re
import typing

from django import forms
from django.contrib import admin, messages
from django.contrib.contenttypes.admin import GenericStackedInline
from django.contrib.contenttypes.models import ContentType
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from django.utils.translation import gettext_lazy as _
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import JsonLexer

from baseapp_ai_langkit.base.utils.model_admin_helper import ModelAdmin
from baseapp_ai_langkit.embeddings.admin_filters import ContentTypeFilter
from baseapp_ai_langkit.embeddings.model_utils import available_content_types_query
from baseapp_ai_langkit.embeddings.models import GenericChunk
from baseapp_ai_langkit.embeddings.tasks import generate_vector_embeddings


def _build_content_object_choices():
    return [
        *[
            (x[0], (*((y, y) for y in x[1]),))
            for x in [
                [
                    f"{ct.app_label}.{ct.model.title()}s",  # HTML <optgroup> title
                    [
                        _encode_content_object_choice(
                            ct.app_label, ct.model, i["pk"]
                        )  # HTML <option> value
                        for i in ct.get_all_objects_for_this_type().order_by("pk").values("pk")
                    ],
                ]
                for ct in ContentType.objects.all().filter(available_content_types_query())
            ]
        ]
    ]


def _encode_content_object_choice(app_label: str, model: str, pk: int) -> str:
    """
    Create a unique string identifying a generic model
    """
    return f"{app_label}.{model}[{pk}]"


def _decode_content_object_choice(encoded: str) -> typing.Tuple[str, str, str]:
    """
    Decode a unique string generated from _encode_content_object_choice(app_label, model, pk)
    """
    result = re.search(r"^(\w+)\.(\w+)\[([\w-]+)\]$", encoded)
    return (result[1], result[2], result[3])


class GenericChunkForm(forms.ModelForm):
    _content_object = forms.ChoiceField(choices=_build_content_object_choices)

    class Meta:
        model = GenericChunk
        fields = (
            "content_type",
            "object_id",
            "_content_object",
        )

    def __init__(self, *args, instance=None, initial={}, **kwargs):
        if instance is not None:
            initial = {
                **initial,
                "_content_object": _encode_content_object_choice(
                    instance.content_type.app_label, instance.content_type.model, instance.object_id
                ),
            }
        super(GenericChunkForm, self).__init__(*args, instance=instance, initial=initial, **kwargs)
        self.fields["content_type"].widget = forms.HiddenInput()
        self.fields["content_type"].required = False
        self.fields["object_id"].widget = forms.HiddenInput()
        self.fields["object_id"].required = False

    def clean(self):
        super(GenericChunkForm, self).clean()
        decoded = _decode_content_object_choice(self.cleaned_data["_content_object"])
        content_type = ContentType.objects.all().get(app_label=decoded[0], model=decoded[1])
        content_object = content_type.get_all_objects_for_this_type().get(pk=decoded[2])
        self.cleaned_data["content_type"] = content_type
        self.cleaned_data["object_id"] = content_object.pk
        del self.cleaned_data["_content_object"]


@admin.register(GenericChunk)
class GenericChunkAdmin(ModelAdmin):
    readonly_fields = ("id",)
    fields = (
        "content_type",
        "object_id",
        "content_object",
        "content",
        "embedding_pretty",
    )
    readonly_fields = ("content", "embedding_pretty")
    list_display = (
        "id",
        "content_type",
        "object_id",
        "content_object",
        "content",
        "has_embedding",
        "created",
    )
    list_filter = (ContentTypeFilter,)
    form = GenericChunkForm

    def has_embedding(self, obj):
        return obj.has_embedding

    def embedding_pretty(self, instance):
        if instance.embedding is None:
            return None
        vector_html = highlight(
            json.dumps(instance.embedding.tolist(), indent=2), JsonLexer(), HtmlFormatter()
        )

        return format_html(
            '<div style="max-height: 300px; overflow: auto;">{}</div>',
            mark_safe(vector_html),
        )

    embedding_pretty.short_description = "Embedding"

    def get_queryset(self, request):
        return super(GenericChunkAdmin, self).get_queryset(request).add_has_embedding()


def GenericChunkInline(**kwargs):
    class _GenericChunkInline(GenericStackedInline):
        model = GenericChunk
        extra = 1
        fields = ["content", "embedding_pretty"]
        readonly_fields = fields

        def embedding_pretty(self, instance):
            if instance.embedding is None:
                return None

            vector_html = highlight(
                json.dumps(instance.embedding.tolist(), indent=2), JsonLexer(), HtmlFormatter()
            )

            return format_html(
                '<div style="max-height: 200px; overflow: auto;">{}</div>',
                mark_safe(vector_html),
            )

        embedding_pretty.short_description = "Embedding"

    for key, value in kwargs.items():
        setattr(_GenericChunkInline, key, value)

    return _GenericChunkInline


class EmbeddableModelAdminMixin(ModelAdmin):
    inlines = [GenericChunkInline(extra=0)]
    actions = ["force_regenerate_embeddings"]

    @admin.action(description="(RAG) Force Regenerate Embeddings")
    def force_regenerate_embeddings(self, request, queryset):
        _count = 0
        for id in queryset.values_list("id", flat=True):
            content_type = ContentType.objects.get_for_model(queryset.model)
            generate_vector_embeddings.delay(
                content_type_app_label=content_type.app_label,
                content_type_model=content_type.model,
                embeddable_id=id,
            )
            _count += 1
        self.message_user(
            request,
            _(
                f"Regenerating embeddings for {_count} {queryset.model._meta.verbose_name_plural.title()}"
            ),
            level=messages.INFO,
        )
