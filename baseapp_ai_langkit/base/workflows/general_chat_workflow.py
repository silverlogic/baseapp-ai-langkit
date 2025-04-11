import logging

from langgraph.graph import END, START

from baseapp_ai_langkit.base.workflows.conversational_workflow import (
    ConversationalWorkflow,
    ConversationState,
)

logger = logging.getLogger(__name__)


class GeneralChatWorkflow(ConversationalWorkflow):
    """
    Generic workflow designed to serve as an example of how to create a funcional new workflow.
    """

    def workflow_node_general_llm(self, state: ConversationState):
        try:
            msg = self.llm.invoke(state["messages"])
            return {"messages": state["messages"] + [msg]}
        except Exception as e:
            logger.exception("Error in the general llm node: %s", e)
            self.error = e
            return {"messages": state["messages"]}

    def setup_workflow_chain(self):
        self.workflow.add_node("general_llm", self.workflow_node_general_llm)
        self.add_memory_summarization_nodes()

        self.workflow.add_edge(START, "general_llm")
        self.add_memory_summarization_edges("general_llm", END)

        super().setup_workflow_chain()
