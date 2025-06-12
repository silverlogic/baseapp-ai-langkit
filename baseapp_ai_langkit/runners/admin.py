from typing import Type, Union

import nested_admin
from django.contrib import admin
from django.utils.safestring import mark_safe

from baseapp_ai_langkit.base.interfaces.llm_node import LLMNodeInterface
from baseapp_ai_langkit.base.prompt_schemas.base_prompt_schema import BasePromptSchema
from baseapp_ai_langkit.base.utils.model_admin_helper import ModelAdmin
from baseapp_ai_langkit.runners.models import (
    LLMRunner,
    LLMRunnerNode,
    LLMRunnerNodeStateModifier,
    LLMRunnerNodeUsagePrompt,
)


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

        return mark_safe(
            f"""
            <div style="background-color: #f9f9f9; border: 1px solid #ddd; padding: 15px; border-radius: 5px; margin-bottom: 15px; overflow-wrap: break-word;">
                <b style="word-wrap: break-word;">Prompt objective:</b>
                <p style="white-space: pre-wrap; word-wrap: break-word;">{prompt_schema.description}</p>
                {required_placeholders_description}
                <b style="word-wrap: break-word;">Default prompt:</b>
                <p style="white-space: pre-wrap; word-wrap: break-word;">{prompt_schema.prompt}</p>
            </div>
            """
        )


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
