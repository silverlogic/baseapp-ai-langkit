import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, List, Optional, Tuple, Type, Union

from langchain_core.language_models import BaseLanguageModel
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver

from baseapp_ai_langkit.base.interfaces.exceptions import LLMChatInterfaceException
from baseapp_ai_langkit.base.interfaces.llm_model_metadata import LLMModelMetadata
from baseapp_ai_langkit.base.interfaces.llm_node import LLMNodeInterface
from baseapp_ai_langkit.base.prompt_schemas.base_prompt_schema import BasePromptSchema
from baseapp_ai_langkit.chats.models import ChatSession


@dataclass
class NodeConfig:
    """Resolved per-node config returned by `BaseRunnerInterface.get_dynamic_node_config`.

    `llm` is None when there is no admin override or when the override was orphaned
    (catalog row missing / initializer unregistered) — callers SHALL substitute the
    runner's default `llm` in that case.
    """

    llm: Optional[BaseLanguageModel]
    usage_prompt_schema: Optional[BasePromptSchema]
    state_modifier_schema: Union[BasePromptSchema, List[BasePromptSchema], None]


if TYPE_CHECKING:
    from baseapp_ai_langkit.base.workflows.base_workflow import BaseWorkflow

logger = logging.getLogger(__name__)


class BaseRunnerInterface(ABC):
    # TODO: change to OrderedDict.
    edge_nodes: dict[str, Type[LLMNodeInterface]] = {}
    nodes: dict[str, Type[LLMNodeInterface]] = {}

    # Single source of truth for the runner's default LLM. The base `initialize_llm`
    # builds the runtime chat model from this via the matching registered initializer
    # (see `LLMModelInitializerRegistry`); the topology extractor reads it declaratively
    # without instantiating any LLM. Subclasses without this declared trigger a Django
    # system check warning (see `runners.checks`).
    default_model_metadata: ClassVar[Optional[LLMModelMetadata]] = None

    def initialize_llm(self) -> BaseLanguageModel:
        """Build the runner's default LLM from `default_model_metadata`.

        Resolves the initializer via `LLMModelInitializerRegistry` and calls
        `initializer.initialize(model_id, **params)`. Subclasses MAY override
        this method to build the LLM imperatively (legacy pattern); the
        recommended approach is to declare `default_model_metadata` and let
        this base implementation build the chat model.
        """
        from baseapp_ai_langkit.runners.model_initializers.registry import (
            LLMModelInitializerRegistry,
        )

        metadata = self.default_model_metadata
        if metadata is None:
            raise NotImplementedError(
                f"{type(self).__name__} must declare `default_model_metadata` "
                "or override `initialize_llm()` to build the runner's default LLM."
            )
        initializer = LLMModelInitializerRegistry.get(metadata.initializer_key)
        if initializer is None:
            raise ValueError(
                f"{type(self).__name__}.default_model_metadata references "
                f"unregistered initializer_key={metadata.initializer_key!r}. "
                "Register it via @register_llm_initializer or pick a built-in."
            )
        return initializer.initialize(metadata.model_id, **(metadata.params or {}))

    @abstractmethod
    def run(self) -> str:
        """
        The LLM interface logic should be implemented here.
        """
        pass

    @classmethod
    @abstractmethod
    def get_workflow_class(cls) -> Type["BaseWorkflow"]:
        """Return the BaseWorkflow subclass this runner uses.

        This is the single source of truth for the runner's workflow class —
        called by the runtime `run()` path AND by `build_topology_workflow()`
        for topology introspection. Subclasses that don't have a workflow class
        (e.g. CLI debugging surfaces) raise `NotImplementedError`; the topology
        endpoint surfaces that as `topology_builder_not_declared`.
        """
        raise NotImplementedError(f"{cls.__name__} did not implement get_workflow_class().")

    @classmethod
    def instantiate_node_for_topology(
        cls,
        node_class: Type[LLMNodeInterface],
        *,
        llm: BaseLanguageModel,
        config: RunnableConfig,
    ) -> LLMNodeInterface:
        """Construct a node for topology extraction. Override if your node class
        needs additional kwargs at __init__ time (e.g. `slack_context=...`).

        Receives stub `llm` / `config` from `topology_extraction_context()`; the
        node MUST be safe to construct from these (no real LLM calls, no DB writes).
        """
        return node_class(llm=llm, config=config)

    @classmethod
    def build_topology_workflow(
        cls,
        *,
        llm: BaseLanguageModel,
        config: RunnableConfig,
        checkpointer: BaseCheckpointSaver,
    ) -> "BaseWorkflow":
        """Build a workflow instance suitable for topology introspection only.

        Default implementation:
            1. Construct each node from `cls.get_available_nodes()` (merged
               `edge_nodes` + `nodes`) via `instantiate_node_for_topology`.
            2. Instantiate `cls.get_workflow_class()` with the supplied stubs
               and the constructed nodes.

        Subclasses whose workflow constructor takes additional kwargs
        (orchestrator, synthesizer, custom state_schema, ...) MUST override this
        method to wire those through. The supplied inputs are guaranteed to be
        safe for shadow compile:
            * llm: a no-op stub that raises if called
            * config: a stub RunnableConfig with no real thread/session
            * checkpointer: an in-memory MemorySaver (never Postgres)

        Runners that don't declare a workflow class raise NotImplementedError
        from `get_workflow_class()`; the topology endpoint surfaces this as
        `topology_builder_not_declared`.
        """
        nodes = {
            key: cls.instantiate_node_for_topology(node_class, llm=llm, config=config)
            for key, node_class in cls.get_available_nodes().items()
        }
        return cls.get_workflow_class()(
            llm=llm,
            config=config,
            checkpointer=checkpointer,
            nodes=nodes,
        )

    def safe_run(self):
        try:
            return self.run()
        except Exception as e:
            logger.error(f"Error in {self.__class__.__name__}: {e}")
            raise LLMChatInterfaceException(e)

    @classmethod
    def get_available_nodes(cls) -> dict[str, Type[LLMNodeInterface]]:
        return {**cls.edge_nodes, **cls.nodes}

    def instantiate_edge_node(self, node_key: str, *args, **kwargs):
        node_class = self.edge_nodes[node_key]
        cfg = self.get_dynamic_node_config(node_key, node_class)
        if cfg.llm is not None:
            kwargs = {**kwargs, "llm": cfg.llm}
        return node_class(
            usage_prompt_schema=cfg.usage_prompt_schema,
            state_modifier_schema=cfg.state_modifier_schema,
            *args,
            **kwargs,
        )

    def get_nodes(self, *args, **kwargs):
        nodes = {}
        for node_key, node_class in self.nodes.items():
            try:
                cfg = self.get_dynamic_node_config(node_key, node_class)
            except Exception as e:
                logger.exception(f"Error in get_dynamic_node_config for {node_key}: {e}")
                cfg = NodeConfig(llm=None, usage_prompt_schema=None, state_modifier_schema=None)
            node_kwargs = kwargs
            if cfg.llm is not None:
                node_kwargs = {**kwargs, "llm": cfg.llm}
            nodes[node_key] = self.instantiate_node(
                node_class,
                usage_prompt_schema=cfg.usage_prompt_schema,
                state_modifier_schema=cfg.state_modifier_schema,
                *args,
                **node_kwargs,
            )
        return nodes

    def get_dynamic_node_config(
        self, node_key: str, node_class: Type[LLMNodeInterface]
    ) -> NodeConfig:
        """Resolve per-node config — prompt schemas + override-built llm (if any).

        Returns prompts via the existing `get_dynamic_prompt_schemas` path; computes
        `llm` from a `LLMRunnerNodeModelOverride` row crosschecked against the
        catalog and the initializer registry. When the override exists but its
        catalog row is missing or its initializer is unregistered, logs a warning
        and returns `llm=None` (caller substitutes the runner's default `llm`).
        """
        usage_prompt_schema, state_modifier_schema = self.get_dynamic_prompt_schemas(
            node_key, node_class
        )
        override_llm = self._build_override_llm(node_key)
        return NodeConfig(
            llm=override_llm,
            usage_prompt_schema=usage_prompt_schema,
            state_modifier_schema=state_modifier_schema,
        )

    def _build_override_llm(self, node_key: str) -> Optional[BaseLanguageModel]:
        from baseapp_ai_langkit.runners.model_initializers.registry import (
            LLMModelInitializerRegistry,
        )
        from baseapp_ai_langkit.runners.models import (
            AvailableLLMModel,
            LLMRunner,
            LLMRunnerNode,
            LLMRunnerNodeModelOverride,
        )

        runner_record = LLMRunner.get_runner_instance_from_runner_class(self.__class__)
        if runner_record is None:
            return None
        try:
            node_record = runner_record.nodes.get(node=node_key)
        except LLMRunnerNode.DoesNotExist:
            return None
        try:
            override = node_record.model_override
        except LLMRunnerNodeModelOverride.DoesNotExist:
            return None

        initializer = LLMModelInitializerRegistry.get(override.initializer_key)
        if initializer is None:
            logger.warning(
                "LLMRunnerNodeModelOverride for runner=%s node=%s references "
                "unregistered initializer_key=%r; falling back to runner default llm",
                runner_record.name,
                node_key,
                override.initializer_key,
            )
            return None

        catalog_row = AvailableLLMModel.objects.filter(
            initializer_key=override.initializer_key,
            model_id=override.model_id,
        ).first()
        if catalog_row is None:
            logger.warning(
                "LLMRunnerNodeModelOverride for runner=%s node=%s references missing "
                "catalog entry %s:%s; falling back to runner default llm",
                runner_record.name,
                node_key,
                override.initializer_key,
                override.model_id,
            )
            return None

        merged_params = {
            **(catalog_row.default_params or {}),
            **(override.params or {}),
        }
        return initializer.initialize(override.model_id, **merged_params)

    def get_dynamic_prompt_schemas(
        self, node_key: str, node_class: Type[LLMNodeInterface]
    ) -> Tuple[BasePromptSchema, Union[list[BasePromptSchema], BasePromptSchema]]:
        from baseapp_ai_langkit.runners.models import (
            LLMRunner,
            LLMRunnerNode,
            LLMRunnerNodeUsagePrompt,
        )

        runner_record = LLMRunner.get_runner_instance_from_runner_class(self.__class__)
        if not runner_record:
            return None, None

        try:
            node_record = runner_record.nodes.get(node=node_key)
        except LLMRunnerNode.DoesNotExist:
            return None, None

        try:
            usage_prompt_record = node_record.usage_prompt
            usage_prompt_schema = usage_prompt_record.get_prompt_schema()
        except LLMRunnerNodeUsagePrompt.DoesNotExist:
            usage_prompt_schema = None

        state_modifiers = node_record.state_modifiers.all()
        state_modifier_schema = node_class.get_static_state_modifier_list()
        for state_modifier in state_modifiers:
            if isinstance(node_class.state_modifier_schema, list):
                state_modifier_schema[state_modifier.index] = state_modifier.get_prompt_schema()
            else:
                state_modifier_schema = state_modifier.get_prompt_schema()
        return usage_prompt_schema, state_modifier_schema

    def instantiate_node(self, node_class: Type[LLMNodeInterface], *args, **kwargs):
        return node_class(*args, **kwargs)


class BaseChatInterface(BaseRunnerInterface):
    def __init__(self, session: ChatSession, user_input: str):
        self.session = session
        self.user_input = user_input
