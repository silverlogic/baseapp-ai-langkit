"""Demo orchestrated chat runner for smoke-testing the runner-admin graph view.

Routes a user prompt through an orchestrator that selects between a book-expert
and a movie-expert worker, then a synthesizer composes the final answer. Lives
in `testproject` so it ships only with the dev/test environment, not the
distributed package.
"""

from typing import Type

from langchain_core.language_models import BaseLanguageModel
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.postgres import PostgresSaver

from baseapp_ai_langkit.base.interfaces.base_runner import BaseChatInterface
from baseapp_ai_langkit.base.interfaces.llm_model_metadata import LLMModelMetadata
from baseapp_ai_langkit.base.prompt_schemas.base_prompt_schema import BasePromptSchema
from baseapp_ai_langkit.base.workers.messages_worker import MessagesWorker
from baseapp_ai_langkit.base.workers.orchestrator_worker import OrchestratorWorker
from baseapp_ai_langkit.base.workers.synthesizer_worker import SynthesizerWorker
from baseapp_ai_langkit.base.workflows.base_workflow import BaseWorkflow
from baseapp_ai_langkit.base.workflows.orchestrated_conversational_workflow import (
    OrchestratedConversationalWorkflow,
)
from baseapp_ai_langkit.chats.checkpointer import LangGraphCheckpointer
from baseapp_ai_langkit.runners.registry import register_runner


class BookExpertWorker(MessagesWorker):
    usage_prompt_schema = BasePromptSchema(
        description=(
            "Book-expert usage prompt. Sent as the human-facing instruction when "
            "the orchestrator routes a query to this worker."
        ),
        prompt=(
            "Please answer the following user question about books, authors, or "
            "literature. Stay focused on the literary medium; defer film or TV "
            "questions to the movie expert."
        ),
    )
    state_modifier_schema = BasePromptSchema(
        description=("Book-expert system prompt. Shapes the worker's voice and scope."),
        prompt=(
            "You are a knowledgeable book expert. Answer questions about literature, "
            "novels, authors, plots, and characters. Be concise and cite sources when "
            "you know them. Only respond about books — if asked about another medium "
            "such as film or TV, say so and let the synthesizer route the rest."
        ),
    )


class MovieExpertWorker(MessagesWorker):
    usage_prompt_schema = BasePromptSchema(
        description=(
            "Movie-expert usage prompt. Sent as the human-facing instruction when "
            "the orchestrator routes a query to this worker."
        ),
        prompt=(
            "Please answer the following user question about films, directors, or "
            "cinema. Stay focused on the cinematic medium; defer book or TV "
            "questions to the relevant expert."
        ),
    )
    state_modifier_schema = BasePromptSchema(
        description=("Movie-expert system prompt. Shapes the worker's voice and scope."),
        prompt=(
            "You are a knowledgeable movie expert. Answer questions about films, "
            "directors, actors, plots, and cinema history. Be concise. Only respond "
            "about films — if asked about another medium such as books or TV, say so "
            "and let the synthesizer route the rest."
        ),
    )


class MusicExpertWorker(MessagesWorker):
    usage_prompt_schema = BasePromptSchema(
        description=(
            "Music-expert usage prompt. Sent as the human-facing instruction when "
            "the orchestrator routes a query to this worker."
        ),
        prompt=(
            "Please answer the following user question about music, artists, "
            "composers, albums, or genres. Stay focused on the musical medium; "
            "defer book, film, or TV questions to the relevant expert."
        ),
    )
    state_modifier_schema = BasePromptSchema(
        description=("Music-expert system prompt. Shapes the worker's voice and scope."),
        prompt=(
            "You are a knowledgeable music expert. Answer questions about songs, "
            "artists, composers, albums, genres, and music history. Be concise. Only "
            "respond about music — if asked about another medium such as books, "
            "films, or TV, say so and let the synthesizer route the rest."
        ),
    )


_NODE_DESCRIPTIONS = {
    "book_expert": (
        "Answers questions about books — literature, novels, authors, plots, characters."
    ),
    "movie_expert": ("Answers questions about films — directors, actors, plots, cinema history."),
    "music_expert": ("Answers questions about music — songs, artists, composers, albums, genres."),
}


class _OrchestratorLLMShim:
    """Topology-only adapter: the topology stub LLM doesn't implement
    `with_structured_output`, but `OrchestratorWorker.__init__` calls it eagerly
    to wrap the model. The shim returns the base stub so construction succeeds;
    nothing ever invokes the result during topology extraction.
    """

    def __init__(self, base: BaseLanguageModel):
        self._base = base

    def with_structured_output(self, *args, **kwargs):
        return self._base

    def __getattr__(self, name):
        return getattr(self._base, name)


@register_runner
class BookMovieExpertChatRunner(BaseChatInterface):
    """Demo orchestrated chat: orchestrator → {book_expert, movie_expert} → synthesizer.

    `nodes` holds the selectable expert workers. `edge_nodes` mirrors the
    LangGraph node keys (`orchestration`, `synthesis`) declared inside
    `OrchestratedConversationalWorkflow.setup_workflow_chain`, so topology
    extraction can include the orchestrator/synthesizer in the rendered graph.
    """

    edge_nodes = {
        "orchestration": OrchestratorWorker,
        "synthesis": SynthesizerWorker,
    }
    nodes = {
        "book_expert": BookExpertWorker,
        "movie_expert": MovieExpertWorker,
        "music_expert": MusicExpertWorker,
    }
    default_model_metadata = LLMModelMetadata(
        initializer_key="openai",
        model_id="gpt-4o-mini",
        params={"temperature": 0},
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config = {"configurable": {"thread_id": str(self.session.id)}}

    @classmethod
    def get_workflow_class(cls) -> Type[BaseWorkflow]:
        return OrchestratedConversationalWorkflow

    def create_checkpointer(self) -> PostgresSaver:
        wrapper = LangGraphCheckpointer()
        wrapper.setup()
        return wrapper.get_checkpointer()

    def run(self) -> str:
        self.llm = self.initialize_llm()
        self.checkpointer = self.create_checkpointer()
        self.nodes = self.get_nodes(llm=self.llm, config=self.config)
        return self.process_workflow()

    def process_workflow(self) -> str:
        workflow = self._build_workflow(
            llm=self.llm,
            config=self.config,
            checkpointer=self.checkpointer,
            node_instances=self.nodes,
        )
        result = workflow.execute(self.user_input)
        return result["messages"][-1].content

    @classmethod
    def build_topology_workflow(
        cls,
        *,
        llm: BaseLanguageModel,
        config: RunnableConfig,
        checkpointer: BaseCheckpointSaver,
    ) -> "BaseWorkflow":
        node_instances = {
            key: cls.instantiate_node_for_topology(node_class, llm=llm, config=config)
            for key, node_class in cls.nodes.items()
        }
        return cls._build_workflow(
            llm=llm,
            config=config,
            checkpointer=checkpointer,
            node_instances=node_instances,
            orchestrator_llm=_OrchestratorLLMShim(llm),
        )

    @classmethod
    def _build_workflow(
        cls,
        *,
        llm: BaseLanguageModel,
        config: RunnableConfig,
        checkpointer: BaseCheckpointSaver,
        node_instances: dict,
        orchestrator_llm: BaseLanguageModel = None,
    ) -> OrchestratedConversationalWorkflow:
        node_info = {
            key: {"description": _NODE_DESCRIPTIONS[key], "node": instance}
            for key, instance in node_instances.items()
        }
        orchestrator = OrchestratorWorker(
            available_nodes_list=list(_NODE_DESCRIPTIONS.items()),
            llm=orchestrator_llm if orchestrator_llm is not None else llm,
            config=config,
        )
        synthesizer = SynthesizerWorker(llm=llm, config=config)
        return cls.get_workflow_class()(
            llm=llm,
            config=config,
            checkpointer=checkpointer,
            nodes=node_info,
            orchestrator=orchestrator,
            synthesizer=synthesizer,
        )
