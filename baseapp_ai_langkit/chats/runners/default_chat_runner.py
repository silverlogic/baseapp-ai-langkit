from langchain_openai import ChatOpenAI
from langgraph.checkpoint.postgres import PostgresSaver

from baseapp_ai_langkit.base.interfaces.base_runner import BaseChatInterface
from baseapp_ai_langkit.base.workers.messages_worker import MessagesWorker
from baseapp_ai_langkit.base.workflows.general_chat_workflow import GeneralChatWorkflow
from baseapp_ai_langkit.chats.checkpointer import LangGraphCheckpointer


class DefaultChatRunner(BaseChatInterface):
    nodes = {
        "general_llm": MessagesWorker,
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config = {"configurable": {"thread_id": str(self.session.id)}}

    def run(self) -> str:
        self.llm = self.initialize_llm()
        self.nodes = self.get_nodes(llm=self.llm, config=self.config)
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
            checkpointer=self.checkpointer,
            nodes=self.nodes,
        )

        response = workflow.execute(self.user_input)
        return response["messages"][-1].content
