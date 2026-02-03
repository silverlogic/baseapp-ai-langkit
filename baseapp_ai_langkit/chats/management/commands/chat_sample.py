import uuid

from django.core.management.base import BaseCommand
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.postgres import PostgresSaver
from pydantic import BaseModel, Field

from baseapp_ai_langkit.base.agents.langgraph_agent import LangGraphAgent
from baseapp_ai_langkit.base.interfaces.console import ConsoleInterface
from baseapp_ai_langkit.base.prompt_schemas.base_prompt_schema import BasePromptSchema
from baseapp_ai_langkit.base.tools.inline_tool import InlineTool
from baseapp_ai_langkit.base.workers.messages_worker import MessagesWorker
from baseapp_ai_langkit.base.workflows.general_chat_workflow import GeneralChatWorkflow
from baseapp_ai_langkit.chats.checkpointer import LangGraphCheckpointer


class EchoToolInput(BaseModel):
    """Input schema for the echo tool."""

    message: str = Field(description="The message to echo back")


class SimpleEchoTool(InlineTool):
    """A simple echo tool that returns the input message."""

    name = "echo"
    description = "A simple tool that echoes back the input message. Use this when you want to repeat or confirm information."
    args_schema = EchoToolInput

    def tool_func(self, message: str) -> str:
        """Echo the input message."""
        return f"Echo: {message}"


class AgentSample(LangGraphAgent):
    state_modifier_schema = BasePromptSchema(
        description="",
        prompt="You are a helpful assistant that can echo back the input message.",
    )
    tools_list = [SimpleEchoTool]


class WorkerSample(MessagesWorker):
    state_modifier_schema = BasePromptSchema(
        description="",
        prompt="You must simply forward the previous LLM response to the user formating the output as a yoda style response.",
    )


class Command(BaseCommand):
    help = "Start a sample chat session using a conversational workflow with an agent and worker chained"

    def __init__(self, *args, **kwargs):
        super(Command, self).__init__(*args, **kwargs)

    def handle(self, *args, **options):
        try:
            self._handle(*args, **options)
        except BaseException as e:
            self.stdout.write("\r\n")
            if isinstance(e, KeyboardInterrupt):
                return
            raise e

    def _handle(self, *args, **options):
        # Initialize LLM
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

        # Create a unique thread ID for this session
        thread_id = str(uuid.uuid4())
        config = {"configurable": {"thread_id": thread_id}}

        # Initialize checkpointer
        checkpointer_wrapper = LangGraphCheckpointer()
        checkpointer_wrapper.setup()
        checkpointer: PostgresSaver = checkpointer_wrapper.get_checkpointer()

        # Chain agent and worker together
        nodes = {
            "simple_agent": AgentSample(llm=llm, config=config),
            "simple_worker": WorkerSample(llm=llm, config=config),
        }

        # Initialize the conversational workflow
        workflow = GeneralChatWorkflow(
            llm=llm,
            checkpointer=checkpointer,
            config=config,
            nodes=nodes,
        )

        # Initialize and run the console interface with the workflow
        console_interface = ConsoleInterface(workflow=workflow)
        console_interface.run()
