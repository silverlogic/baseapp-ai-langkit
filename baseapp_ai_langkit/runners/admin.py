from typing import Type, Union

import nested_admin
from django.contrib import admin
from django.utils.safestring import mark_safe

from baseapp_ai_langkit.base.interfaces.llm_node import LLMNodeInterface
from baseapp_ai_langkit.base.prompt_schemas.base_prompt_schema import BasePromptSchema
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
        if self._has_usage_prompt(obj):
            return (
                "description",
                "usage_prompt",
            )
        return ("notice",)

    def get_readonly_fields(self, request, obj=None):
        if self._has_usage_prompt(obj):
            return ("description",)
        return ("notice",)

    def _has_usage_prompt(self, obj) -> bool:
        """Whether this inline has a usage prompt to edit.

        ``obj`` is the object the change view is for, which for a nested inline is the root
        :class:`LLMRunner` and not this inline's own parent: Django builds an inline's
        fieldsets once per formset, not once per row. Reading ``obj.usage_prompt`` therefore
        raised ``AttributeError`` on **every** runner change page, and the ``DoesNotExist``
        this used to catch could never fire.

        ``sync_runners`` creates a usage prompt row only for a node that declares a
        ``usage_prompt_schema``, so the question is whether any row exists under the object
        being edited. A runner whose nodes disagree gets the editable fields, and the nodes
        without a row simply render no form; that is a cosmetic imprecision rather than the
        crash it replaces.
        """
        if isinstance(obj, LLMRunner):
            return LLMRunnerNodeUsagePrompt.objects.filter(runner_node__runner=obj).exists()
        if isinstance(obj, LLMRunnerNode):
            # Not what Django passes today, but it is what this code was written for, so a
            # nested_admin that starts passing the immediate parent keeps working.
            return LLMRunnerNodeUsagePrompt.objects.filter(runner_node=obj).exists()
        return False

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
class LLMRunnerAdmin(nested_admin.NestedModelAdmin):
    """The prompt editor: a runner, its nodes, and each node's prompts, three levels deep.

    Deliberately **not** mixed with unfold's ``ModelAdmin``, which is otherwise this project's
    convention. The two do not compose: with unfold in the MRO, rendering any nested inline
    raises ``AttributeError: 'InlineAdminFormSet' object has no attribute 'initial_forms'``
    from ``django.contrib.admin.helpers``, because unfold hands the nested formset where
    Django expects a plain one. Verified against unfold and django-nested-admin 4.1.6 on
    Django 5.2 by removing unfold and nothing else: every runner change page went from 500 to
    200. ``unfold.contrib.inlines`` does not help, being about nonrelated inlines.

    The page therefore renders with the stock admin form widgets inside unfold's site chrome.
    That is the trade: a prompt editor that works, styled less well.
    """

    list_display = ("name",)
    search_fields = ("name",)
    ordering = ("name",)
    readonly_fields = ("name",)
    inlines = [LLMRunnerNodeInline]
