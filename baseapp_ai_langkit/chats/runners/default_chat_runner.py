from typing import Type

from langgraph.checkpoint.postgres import PostgresSaver

from baseapp_ai_langkit.base.interfaces.base_runner import BaseChatInterface
from baseapp_ai_langkit.base.interfaces.llm_model_metadata import LLMModelMetadata
from baseapp_ai_langkit.base.workers.messages_worker import MessagesWorker
from baseapp_ai_langkit.base.workflows.base_workflow import BaseWorkflow
from baseapp_ai_langkit.base.workflows.general_chat_workflow import GeneralChatWorkflow
from baseapp_ai_langkit.chats.checkpointer import LangGraphCheckpointer
from baseapp_ai_langkit.runners.registry import register_runner


@register_runner
class DefaultChatRunner(BaseChatInterface):
    label = "Default chat"
    description = (
        "Single-node general-purpose chat runner. Routes the user's input through one "
        "MessagesWorker backed by the runner's default LLM, with no orchestrator or "
        "specialist workers. The drop-in starting point for new chat sessions in any "
        "consumer project; replace or extend by registering a custom runner."
    )
    nodes = {
        "general_llm": MessagesWorker,
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
        return GeneralChatWorkflow

    def run(self) -> str:
        self.llm = self.initialize_llm()
        self.nodes = self.get_nodes(llm=self.llm, config=self.config)
        self.checkpointer = self.create_checkpointer()
        response = self.process_workflow()
        return response

    def create_checkpointer(self) -> PostgresSaver:
        checkpointer_wrapper = LangGraphCheckpointer()
        checkpointer_wrapper.setup()
        return checkpointer_wrapper.get_checkpointer()

    def process_workflow(self):
        workflow = self.get_workflow_class()(
            llm=self.llm,
            config=self.config,
            checkpointer=self.checkpointer,
            nodes=self.nodes,
        )

        response = workflow.execute(self.user_input)
        return response["messages"][-1].content
