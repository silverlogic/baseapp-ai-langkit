from langchain.base_language import BaseLanguageModel
from langchain_core.messages import HumanMessage, RemoveMessage, SystemMessage
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.graph import END, MessagesState

from baseapp_ai_langkit.base.workflows.base_workflow import BaseWorkflow


class ConversationState(MessagesState):
    summary: str


class ConversationalWorkflow(BaseWorkflow):
    """
    Workflow with memory to store the conversation state.
    This is an abstract class that provides helpful methods to handle memory.

    The workflow that extends this class should use the follow methods in the setup_workflow_chain
    implementation:
    - add_memory_summarization_nodes
    - add_memory_summarization_edges

    Args:
        llm (BaseLanguageModel): The llm to exec the summarization node.
        checkpointer (PostgresSaver): The checkpointer to store the conversation state.
        max_messages (int): Defines the limit to trigger the summarization node.
        retained_messages (int): Defines the number of messages to keep in the memory.
    """

    llm: BaseLanguageModel
    checkpointer: PostgresSaver
    max_messages: int
    retained_messages: int

    error: Exception = None

    def __init__(
        self,
        llm: BaseLanguageModel,
        checkpointer: PostgresSaver,
        max_messages: int = 6,
        retained_messages: int = 2,
        *args,
        **kwargs,
    ):
        self.llm = llm
        self.checkpointer = checkpointer
        self.max_messages = max_messages
        self.retained_messages = retained_messages
        super().__init__(*args, **kwargs)

    @property
    def state_graph_schema(self):
        return ConversationState

    def setup_workflow_chain(self):
        self.workflow_chain = self.workflow.compile(checkpointer=self.checkpointer)

    def workflow_node_maybe_rollback_memory(self, state: ConversationState):
        if self.error:
            state["messages"] = state["messages"] + [RemoveMessage(id=state["messages"][-1].id)]
        return state

    def workflow_node_summarize_conversation(self, state: ConversationState):
        summary = state.get("summary", "")
        if summary:
            summary_message = (
                f"This is the summary of the conversation so far: {summary}\n\n"
                "Extend the summary by taking into account the new messages above:"
            )
        else:
            summary_message = (
                "Summarize the conversation above, remember to keep key information about the user:"
            )

        # 1. Create summary prompt invoke.
        summarization_prompt = HumanMessage(content=summary_message)
        messages_for_llm = state["messages"] + [summarization_prompt]
        summary_response = self.llm.invoke(messages_for_llm)
        new_summary = summary_response.content

        # 2. Select the messages we want to keep.
        messages_to_keep = state["messages"][-self.retained_messages :]
        reinserted_messages = []
        for msg in messages_to_keep:
            new_msg = msg.model_copy(update={"id": None})
            reinserted_messages.append(new_msg)

        # 3. Remove all messages from the state (needed since the summary would be mandatorily inserted at the end).
        remove_all = [RemoveMessage(id=m.id) for m in state["messages"]]

        # 4. Create the summary message that would appear at the top of the conversation.
        new_summary_message = SystemMessage(
            content=f"Updated conversation summary:\n\n{new_summary}"
        )

        # 5. Update the state.
        return {
            "summary": new_summary,
            "messages": remove_all + [new_summary_message] + reinserted_messages,
        }

    def add_memory_summarization_nodes(self):
        self.workflow.add_node("maybe_rollback_memory", self.workflow_node_maybe_rollback_memory)
        self.workflow.add_node("summarize_conversation", self.workflow_node_summarize_conversation)

    def add_memory_summarization_edges(self, start_point: str, end_point: str = END):
        self.workflow.add_edge(start_point, "maybe_rollback_memory")
        self.workflow.add_conditional_edges(
            "maybe_rollback_memory",
            self.get_should_summarize_conditional_edge(end_point),
            ["summarize_conversation", end_point],
        )
        self.workflow.add_edge("summarize_conversation", end_point)

    def get_should_summarize_conditional_edge(self, end_point: str) -> str:
        """
        Returns a function that determines if the conversation should be summarized.
        It uses the internal method in order to access the end_point variable.
        """

        def should_summarize(state: ConversationState) -> str:
            if self.error:
                return end_point
            messages = state["messages"]
            return "summarize_conversation" if len(messages) > self.max_messages else end_point

        return should_summarize

    def execute(self, prompt: str):
        input_message = HumanMessage(content=prompt)
        result = self.workflow_chain.invoke({"messages": [input_message]}, self.config)

        if self.error:
            raise self.error

        return result
