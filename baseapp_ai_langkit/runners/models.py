import logging
from typing import Optional, Type

from django.core.exceptions import ValidationError
from django.db import models
from model_utils.models import TimeStampedModel

from baseapp_ai_langkit.base.interfaces.base_runner import BaseRunnerInterface
from baseapp_ai_langkit.base.interfaces.llm_node import LLMNodeInterface
from baseapp_ai_langkit.base.prompt_schemas.base_prompt_schema import BasePromptSchema
from baseapp_ai_langkit.runners.registry import RunnerRegistry

logger = logging.getLogger(__name__)


class LLMRunner(models.Model):
    name = models.CharField(max_length=255, unique=True)

    def __str__(self):
        return self.name

    @property
    def runner_class(self) -> Type[BaseRunnerInterface]:
        for runner_class in RunnerRegistry.get_all():
            if f"{runner_class.__module__}.{runner_class.__name__}" == self.name:
                return runner_class
        raise ValueError(f"Runner {self.name} not found")

    def get_nodes_dict(self) -> dict[str, Type[LLMNodeInterface]]:
        return self.runner_class.get_available_nodes()

    @classmethod
    def get_runner_instance_from_runner_class(
        cls, runner_class: Type[BaseRunnerInterface]
    ) -> Optional[Type[BaseRunnerInterface]]:
        try:
            runner_instance = cls.objects.get(
                name=f"{runner_class.__module__}.{runner_class.__name__}"
            )
            return runner_instance
        except cls.DoesNotExist:
            return None

    @classmethod
    def sync_runners(cls):
        runners = RunnerRegistry.get_all()
        existing_runners = set()
        existing_nodes = set()
        existing_usage_prompts = set()
        existing_state_modifiers = set()
        for runner in runners:
            llm_runner, created = cls.objects.get_or_create(
                name=f"{runner.__module__}.{runner.__name__}",
            )
            existing_runners.add(llm_runner.id)
            if created:
                logger.info(f"Runner {runner.__name__} created.")
            nodes_dict = runner.get_available_nodes()
            for node_name, node_class in nodes_dict.items():
                if not node_class.state_modifier_schema:
                    continue
                llm_runner_node, created = LLMRunnerNode.objects.get_or_create(
                    runner=llm_runner,
                    node=node_name,
                )
                existing_nodes.add(llm_runner_node.id)
                if created:
                    logger.info(f"Runner node {node_name} created.")
                if hasattr(node_class, "usage_prompt_schema") and node_class.usage_prompt_schema:
                    llm_runner_node_usage_prompt, created = (
                        LLMRunnerNodeUsagePrompt.objects.get_or_create(
                            runner_node=llm_runner_node, defaults={"usage_prompt": ""}
                        )
                    )
                    existing_usage_prompts.add(llm_runner_node_usage_prompt.id)
                    if created:
                        logger.info(f"Usage prompt {node_name} created.")
                state_modifier_list = node_class.get_static_state_modifier_list()
                for i, state_modifier in enumerate(state_modifier_list):
                    llm_runner_node_state_modifier, created = (
                        LLMRunnerNodeStateModifier.objects.get_or_create(
                            runner_node=llm_runner_node,
                            index=i,
                            defaults={"state_modifier": ""},
                        )
                    )
                    existing_state_modifiers.add(llm_runner_node_state_modifier.id)
                    if created:
                        logger.info(f"State modifier {node_name} - {i} created.")
        cls.delete_unused_runners(
            existing_runners, existing_nodes, existing_usage_prompts, existing_state_modifiers
        )

    @classmethod
    def delete_unused_runners(
        cls, existing_runners, existing_nodes, existing_usage_prompts, existing_state_modifiers
    ):
        for state_modifier in LLMRunnerNodeStateModifier.objects.exclude(
            id__in=existing_state_modifiers
        ):
            state_modifier.delete()
            logger.info(
                f"Deleted state modifier {state_modifier.id} {state_modifier.runner_node.runner.name} {state_modifier.runner_node.node} {state_modifier.index}"
            )
        for usage_prompt in LLMRunnerNodeUsagePrompt.objects.exclude(id__in=existing_usage_prompts):
            usage_prompt.delete()
            logger.info(
                f"Deleted usage prompt {usage_prompt.id} {usage_prompt.runner_node.runner.name} {usage_prompt.runner_node.node}"
            )
        for node_id in LLMRunnerNode.objects.exclude(id__in=existing_nodes):
            node_id.delete()
            logger.info(f"Deleted node {node_id.id} {node_id.runner.name} {node_id.node}")
        for runner_id in cls.objects.exclude(id__in=existing_runners):
            runner_id.delete()
            logger.info(f"Deleted runner {runner_id.id} {runner_id.name}")


class LLMRunnerNode(TimeStampedModel):
    runner = models.ForeignKey(LLMRunner, on_delete=models.CASCADE, related_name="nodes")
    node = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.runner.name} - {self.node}"


class LLMRunnerNodeUsagePrompt(TimeStampedModel):
    runner_node = models.OneToOneField(
        LLMRunnerNode, on_delete=models.CASCADE, related_name="usage_prompt"
    )
    usage_prompt = models.TextField(
        null=True,
        blank=True,
        help_text="The prompt that will be used to explain the LLM orchestrator of how to use the node.",
    )

    def __str__(self):
        return (
            f"{self.runner_node.runner.name} - {self.runner_node.node} - {self.usage_prompt[:30]}"
        )

    def clean_usage_prompt(self):
        if self.usage_prompt:
            nodes_dict = self.runner_node.runner.get_nodes_dict()
            node: Optional[Type[LLMNodeInterface]] = nodes_dict.get(self.runner_node.node, None)
            if node and not node.usage_prompt_schema.validate(self.usage_prompt):
                raise ValidationError("The usage prompt is not using all required placeholders.")

    def clean(self):
        self.clean_usage_prompt()
        super().clean()

    def get_prompt_schema(self):
        nodes_dict = self.runner_node.runner.get_nodes_dict()
        node: Optional[Type[LLMNodeInterface]] = nodes_dict.get(self.runner_node.node)
        if self.usage_prompt and node.usage_prompt_schema.validate(self.usage_prompt):
            usage_prompt_schema = node.get_static_usage_prompt()
            usage_prompt_schema.prompt = self.usage_prompt
            return usage_prompt_schema
        return node.usage_prompt_schema

    class Meta:
        unique_together = ("runner_node", "usage_prompt")
        verbose_name = "Usage prompt"
        verbose_name_plural = "Usage prompts"


class LLMRunnerNodeStateModifier(TimeStampedModel):
    runner_node = models.ForeignKey(
        LLMRunnerNode, on_delete=models.CASCADE, related_name="state_modifiers"
    )
    index = models.IntegerField()
    state_modifier = models.TextField(
        null=True, blank=True, help_text="The state modifier that will be used to modify the state."
    )

    def __str__(self):
        return f"{self.runner_node.runner.name} - {self.runner_node.node} - {self.index}"

    def clean_state_modifier(self):
        if self.state_modifier:
            nodes_dict = self.runner_node.runner.get_nodes_dict()
            node: Optional[Type[LLMNodeInterface]] = nodes_dict.get(self.runner_node.node, None)
            state_modifiers = node.get_static_state_modifier_list()
            state_modifier: BasePromptSchema = state_modifiers[self.index]
            if node and not state_modifier.validate(self.state_modifier):
                raise ValidationError("The state modifier is not using all required placeholders.")

    def clean(self):
        self.clean_state_modifier()
        super().clean()

    def get_prompt_schema(self):
        nodes_dict = self.runner_node.runner.get_nodes_dict()
        node: Optional[Type[LLMNodeInterface]] = nodes_dict.get(self.runner_node.node, None)
        state_modifiers = node.get_static_state_modifier_list()
        state_modifier_schema: BasePromptSchema = state_modifiers[self.index]
        if self.state_modifier and state_modifier_schema.validate(self.state_modifier):
            state_modifier_schema.prompt = self.state_modifier
        return state_modifier_schema

    class Meta:
        unique_together = ("runner_node", "index")
        verbose_name = "State modifier"
        verbose_name_plural = "State modifiers"
        ordering = ["index"]
