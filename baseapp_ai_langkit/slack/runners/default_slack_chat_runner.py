from langchain_openai import ChatOpenAI
from langgraph.checkpoint.postgres import PostgresSaver

from baseapp_ai_langkit.base.workflows.general_chat_workflow import GeneralChatWorkflow
from baseapp_ai_langkit.chats.checkpointer import LangGraphCheckpointer
from baseapp_ai_langkit.slack.base.interfaces.slack_chat_runner import (
    BaseSlackChatInterface,
)
from baseapp_ai_langkit.slack.base.workers.default_slack_worker import (
    DefaultSlackWorker,
)


class DefaultSlackChatRunner(BaseSlackChatInterface):
    nodes = {
        "slack_worker": DefaultSlackWorker,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config = {"configurable": {"thread_id": str(self.session.id)}}

    def run(self) -> str:
        self.llm = self.initialize_llm()
        self.nodes = self.get_nodes(
            slack_context=self.slack_context, llm=self.llm, config=self.config
        )
        self.checkpointer = self.create_checkpointer()
        response = self.process_workflow()
        return response

    def initialize_llm(self) -> ChatOpenAI:
        return ChatOpenAI(model="gpt-3.5-turbo", temperature=0)

    def create_checkpointer(self) -> PostgresSaver:
        checkpointer_wrapper = LangGraphCheckpointer()
        checkpointer_wrapper.setup()
        return checkpointer_wrapper.get_checkpointer()

    def process_workflow(self):
        workflow = GeneralChatWorkflow(
            llm=self.llm,
            config=self.config,
            nodes=self.nodes,
            checkpointer=self.checkpointer,
        )

        response = workflow.execute(self.user_input)
        return response["messages"][-1].content
