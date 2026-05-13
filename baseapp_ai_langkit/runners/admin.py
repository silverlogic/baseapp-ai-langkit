from typing import Type, Union

import nested_admin
from django import forms
from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.http import HttpResponseNotAllowed
from django.template.response import TemplateResponse
from django.urls import path, reverse
from django.utils.http import unquote
from django.utils.safestring import mark_safe

from baseapp_ai_langkit import __version__
from baseapp_ai_langkit.base.interfaces.llm_node import LLMNodeInterface
from baseapp_ai_langkit.base.prompt_schemas.base_prompt_schema import BasePromptSchema
from baseapp_ai_langkit.base.utils.model_admin_helper import ModelAdmin
from baseapp_ai_langkit.runners.model_initializers.registry import (
    LLMModelInitializerRegistry,
)
from baseapp_ai_langkit.runners.models import (
    AvailableLLMModel,
    LLMRunner,
    LLMRunnerNode,
    LLMRunnerNodeModelOverride,
    LLMRunnerNodeStateModifier,
    LLMRunnerNodeUsagePrompt,
)
from baseapp_ai_langkit.runners.topology.save_views import (
    save_model_override,
    save_state_modifier,
    save_topology_layout,
    save_usage_prompt,
)
from baseapp_ai_langkit.runners.topology.views import topology_view


class AddAndDeleteBlockerMixin:
    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class PromptDescriptionMixin:
    def description(self, obj: Union[LLMRunnerNodeUsagePrompt, LLMRunnerNodeStateModifier]):
        prompt_schema = self.get_prompt_schema(obj)
        return self._get_prompt_description(prompt_schema)

    def get_prompt_schema(
        self, obj: Union[LLMRunnerNodeUsagePrompt, LLMRunnerNodeStateModifier]
    ) -> BasePromptSchema:
        raise NotImplementedError

    def _get_prompt_description(self, prompt_schema: BasePromptSchema):
        if prompt_schema.required_placeholders:
            required_placeholders_description = f"""
                <b style="word-wrap: break-word;">Required placeholders (mandatory keys that must be present in the prompt):</b>
                <p style="word-wrap: break-word;">{', '.join([f'{{{placeholder}}}' for placeholder in prompt_schema.required_placeholders])}</p>
            """
        else:
            required_placeholders_description = ""

        return mark_safe(f"""
            <div style="background-color: #f9f9f9; border: 1px solid #ddd; padding: 15px; border-radius: 5px; margin-bottom: 15px; overflow-wrap: break-word;">
                <b style="word-wrap: break-word;">Prompt objective:</b>
                <p style="white-space: pre-wrap; word-wrap: break-word;">{prompt_schema.description}</p>
                {required_placeholders_description}
                <b style="word-wrap: break-word;">Default prompt:</b>
                <p style="white-space: pre-wrap; word-wrap: break-word;">{prompt_schema.prompt}</p>
            </div>
            """)


class LLMRunnerNodeUsagePromptInline(
    PromptDescriptionMixin, AddAndDeleteBlockerMixin, nested_admin.NestedStackedInline
):
    model = LLMRunnerNodeUsagePrompt
    is_sortable = False

    def get_fields(self, request, obj=None):
        fields = (
            "description",
            "usage_prompt",
        )
        try:
            obj and obj.usage_prompt
        except LLMRunnerNodeUsagePrompt.DoesNotExist:
            fields = ("notice",)
        return fields

    def get_readonly_fields(self, request, obj=None):
        readonly_fields = ("description",)
        try:
            obj and obj.usage_prompt
        except LLMRunnerNodeUsagePrompt.DoesNotExist:
            readonly_fields = ("notice",)
        return readonly_fields

    def notice(self, obj: LLMRunnerNodeUsagePrompt):
        return mark_safe("<i>There is no usage prompt for this node.</i>")

    def get_prompt_schema(self, obj: LLMRunnerNodeUsagePrompt) -> BasePromptSchema:
        node_obj: Type[LLMNodeInterface] = obj.runner_node.runner.get_nodes_dict()[
            obj.runner_node.node
        ]
        return node_obj.usage_prompt_schema

    class Media:
        css = {
            "all": [
                "css/custom_nested_admin.css",
            ]
        }


class LLMRunnerNodeStateModifierInline(
    PromptDescriptionMixin, AddAndDeleteBlockerMixin, nested_admin.NestedStackedInline
):
    model = LLMRunnerNodeStateModifier
    is_sortable = False
    fields = (
        "description",
        "state_modifier",
    )
    readonly_fields = ("description",)

    def get_prompt_schema(self, obj: LLMRunnerNodeStateModifier) -> BasePromptSchema:
        node_obj: Type[LLMNodeInterface] = obj.runner_node.runner.get_nodes_dict()[
            obj.runner_node.node
        ]
        state_modifier_list = node_obj.get_static_state_modifier_list()
        return state_modifier_list[obj.index]

    class Media:
        css = {
            "all": [
                "css/custom_nested_admin.css",
            ]
        }


class LLMRunnerNodeInline(AddAndDeleteBlockerMixin, nested_admin.NestedStackedInline):
    model = LLMRunnerNode
    fields = ("node",)
    readonly_fields = ("node",)
    inlines = [LLMRunnerNodeUsagePromptInline, LLMRunnerNodeStateModifierInline]
    is_sortable = False


@admin.register(LLMRunner)
class LLMRunnerAdmin(nested_admin.NestedModelAdmin, ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)
    ordering = ("name",)
    readonly_fields = ("name",)
    inlines = [LLMRunnerNodeInline]

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "<int:pk>/topology/",
                self.admin_site.admin_view(topology_view),
                name="baseapp_ai_langkit_runners_llmrunner_topology",
            ),
            path(
                "<int:pk>/change/legacy/",
                self.admin_site.admin_view(self.legacy_change_view),
                name="baseapp_ai_langkit_runners_llmrunner_change_legacy",
            ),
            path(
                "<int:pk>/topology/nodes/<str:node_key>/usage-prompt/",
                self.admin_site.admin_view(save_usage_prompt),
                name="baseapp_ai_langkit_runners_llmrunner_save_usage_prompt",
            ),
            path(
                "<int:pk>/topology/nodes/<str:node_key>/state-modifiers/<int:state_modifier_index>/",
                self.admin_site.admin_view(save_state_modifier),
                name="baseapp_ai_langkit_runners_llmrunner_save_state_modifier",
            ),
            path(
                "<int:pk>/topology/layout/",
                self.admin_site.admin_view(save_topology_layout),
                name="baseapp_ai_langkit_runners_llmrunner_save_topology_layout",
            ),
            path(
                "<int:pk>/topology/nodes/<str:node_key>/model/",
                self.admin_site.admin_view(save_model_override),
                name="baseapp_ai_langkit_runners_llmrunner_save_model_override",
            ),
        ]
        return custom_urls + urls

    def legacy_change_view(self, request, pk):
        return super(LLMRunnerAdmin, self).change_view(request, str(pk))

    def change_view(self, request, object_id, form_url="", extra_context=None):
        if request.method != "GET":
            return HttpResponseNotAllowed(["GET"])

        obj = self.get_object(request, unquote(object_id))
        if obj is None:
            return self._get_obj_does_not_exist_redirect(request, self.opts, object_id)
        if not self.has_view_permission(request, obj):
            raise PermissionDenied

        topology_url = reverse("admin:baseapp_ai_langkit_runners_llmrunner_topology", args=[obj.pk])
        legacy_admin_url = reverse(
            "admin:baseapp_ai_langkit_runners_llmrunner_change_legacy", args=[obj.pk]
        )

        context = {
            **self.admin_site.each_context(request),
            "title": str(obj),
            "subtitle": None,
            "opts": self.opts,
            "original": obj,
            "object_id": object_id,
            "is_popup": False,
            "media": self.media,
            "preserved_filters": self.get_preserved_filters(request),
            "topology_url": topology_url,
            "legacy_admin_url": legacy_admin_url,
            "pkg_version": __version__,
        }
        if extra_context:
            context.update(extra_context)

        return TemplateResponse(
            request,
            "admin/baseapp_ai_langkit_runners/llmrunner/graph.html",
            context,
        )


class _InitializerKeyChoiceForm(forms.ModelForm):
    """Renders `initializer_key` as a dropdown sourced from the live registry.

    Choices are computed at form-class instantiation (each admin request) so a
    project that registers a custom initializer at startup sees it in the
    dropdown without a restart-induced cache miss.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        choices = [
            (init.key, f"{init.label} ({init.key})")
            for init in LLMModelInitializerRegistry.get_all()
        ]
        # Keep an existing value addressable even if its initializer was
        # removed from the registry — operators need to see and correct it
        # rather than have the form silently swap it.
        current = self.instance.initializer_key if self.instance else None
        if current and current not in {key for key, _ in choices}:
            choices.append((current, f"{current} (not registered)"))
        self.fields["initializer_key"] = forms.ChoiceField(
            choices=sorted(choices, key=lambda c: c[1]),
            help_text=self.fields["initializer_key"].help_text,
        )


class AvailableLLMModelForm(_InitializerKeyChoiceForm):
    class Meta:
        model = AvailableLLMModel
        fields = "__all__"


class LLMRunnerNodeModelOverrideForm(_InitializerKeyChoiceForm):
    class Meta:
        model = LLMRunnerNodeModelOverride
        fields = "__all__"


@admin.register(AvailableLLMModel)
class AvailableLLMModelAdmin(admin.ModelAdmin):
    form = AvailableLLMModelForm
    list_display = ("label", "initializer_key", "model_id")
    search_fields = ("label", "model_id")
    list_filter = ("initializer_key",)
    ordering = ("initializer_key", "model_id")


@admin.register(LLMRunnerNodeModelOverride)
class LLMRunnerNodeModelOverrideAdmin(admin.ModelAdmin):
    form = LLMRunnerNodeModelOverrideForm
    list_display = ("runner_node", "initializer_key", "model_id", "modified")
    search_fields = ("runner_node__node", "runner_node__runner__name")
    readonly_fields = ("runner_node",)
    list_filter = ("initializer_key",)
