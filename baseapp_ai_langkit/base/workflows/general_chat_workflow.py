import logging

from baseapp_ai_langkit.base.interfaces.llm_node import LLMNodeInterface
from baseapp_ai_langkit.base.workflows.chain_of_nodes_mixin import ChainOfNodesMixin
from baseapp_ai_langkit.base.workflows.conversational_workflow import (
    ConversationalWorkflow,
    ConversationState,
)

logger = logging.getLogger(__name__)


class GeneralChatWorkflow(ChainOfNodesMixin, ConversationalWorkflow):
    """
    Generic workflow designed to serve as an example of how to create a funcional new workflow.
    """

    def __init__(
        self,
        nodes: dict[str, LLMNodeInterface],
        *args,
        **kwargs,
    ):
        self.nodes = nodes
        super().__init__(*args, **kwargs)

    def setup_workflow_chain(self):
        self.setup_chain_of_nodes()
        super().setup_workflow_chain()

    def invoke_node(self, node: LLMNodeInterface):
        def format_output(state: ConversationState):
            messages = state["messages"]
            response = node.invoke(messages, state)
            return {"messages": messages + [response]}

        return format_output
