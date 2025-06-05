import logging
import operator
from typing import Annotated, TypedDict, Union

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.constants import Send
from langgraph.graph import END, START

from baseapp_ai_langkit.base.agents.langgraph_agent import LangGraphAgent
from baseapp_ai_langkit.base.workers.messages_worker import MessagesWorker
from baseapp_ai_langkit.base.workers.orchestrator_worker import (
    AvailableNode,
    OrchestratorWorker,
)
from baseapp_ai_langkit.base.workers.synthesizer_worker import SynthesizerWorker
from baseapp_ai_langkit.base.workflows.conversational_workflow import (
    ConversationalWorkflow,
    ConversationState,
)

logger = logging.getLogger(__name__)


class NodeInfo(TypedDict):
    description: str
    node: Union[LangGraphAgent, MessagesWorker]


class OrchestratorState(ConversationState):
    selected_nodes: Annotated[list[AvailableNode], operator.add]
    completed_nodes: Annotated[list[str], operator.add]
    synthesizer_context: str


class NodeScopeState:
    node_key: str
    custom_prompt: str


class OrchestratedConversationalWorkflow(ConversationalWorkflow):
    """
    OrchestratedConversationalWorkflow is a workflow that orchestrates a list of nodes.
    It's designed to be used when you need to orchestrate a list of nodes to answer the user prompt.

    Args:
        nodes (dict[str, Union[NodeInfo]]): A dictionary of nodes to orchestrate.
        orchestrator (OrchestratorWorker): The orchestrator to use for the workflow.
        synthesizer (SynthesizerWorker): The synthesizer to use for the workflow.
    """

    # TODO: It should be able to go straight to END if the orchestrator Guardrails say so.

    nodes: dict[str, Union[NodeInfo]]
    orchestrator: OrchestratorWorker
    synthesizer: SynthesizerWorker

    @property
    def state_graph_schema(self):
        return OrchestratorState

    def __init__(
        self,
        nodes: dict[str, Union[NodeInfo]],
        orchestrator: OrchestratorWorker,
        synthesizer: SynthesizerWorker,
        *args,
        **kwargs,
    ):
        self.nodes = nodes
        self.orchestrator = orchestrator
        self.synthesizer = synthesizer
        super().__init__(*args, **kwargs)

    def workflow_node_orchestration(self, state: OrchestratorState):
        try:
            orchestrator_response = self.orchestrator.invoke(state["messages"])

            selected_nodes = []
            for node in orchestrator_response.nodes:
                if node.name in self.nodes:
                    selected_nodes.append(node)

            return {
                "messages": state["messages"],
                "selected_nodes": selected_nodes,
                "synthesizer_context": orchestrator_response.synthesizer_context,
            }
        except Exception as e:
            logger.exception("Error in orchestration node: %s", e)
            self.error = e
            return state

    def workflow_node_call_node(self, state: NodeScopeState):
        node_key = state["node_key"]
        node = self.nodes[node_key]["node"]
        try:
            response = node.invoke(
                messages=[
                    HumanMessage(content=state["custom_prompt"]),
                ],
            )
            return {"completed_nodes": [f"{node_key} response: {response.content}"]}
        except Exception as e:
            logger.exception("Error in the node %s: %s", node_key, e)
            return {
                "completed_nodes": [
                    f"{node_key} error: {e}"
                    "\nLet the user know that this error happened without technicalities or technical details."
                ]
            }

    def workflow_node_synthesis(self, state: OrchestratorState):
        try:
            nodes_keys = [node.name for node in state["selected_nodes"]]
            selected_nodes = {key: value for key, value in self.nodes.items() if key in nodes_keys}
            selected_nodes_list = "\n".join(
                [
                    f"> Worker/Agent name: {node_key} - How to use it: {node['description']}"
                    for node_key, node in selected_nodes.items()
                ]
            )
            synthesizer_context = state["synthesizer_context"]
            user_prompt = state["messages"][-1].content

            messages = [
                AIMessage(content=worker_output) for worker_output in state["completed_nodes"]
            ]

            response = self.synthesizer.invoke(
                messages=(
                    messages
                    if len(messages) > 0
                    else [
                        HumanMessage(
                            content="Follow the orchestrator instructions to answer the user message."
                        )
                    ]
                ),
                state={
                    "user_prompt": user_prompt,
                    "synthesizer_context": synthesizer_context,
                    "selected_nodes_list": selected_nodes_list,
                },
            )

            # Clearing is a safety measure to make sure the checkpointer is not storing those
            # states. However, two concurrent requests from a same session will share this state.
            state["selected_nodes"].clear()
            state["completed_nodes"].clear()

            return {
                "messages": state["messages"] + [response],
                "selected_nodes": [],
                "completed_nodes": [],
            }
        except Exception as e:
            logger.exception("Error in the synthesis node: %s", e)
            self.error = e
            state["selected_nodes"].clear()
            state["completed_nodes"].clear()
            return {
                **state,
                "selected_nodes": [],
                "completed_nodes": [],
            }

    def workflow_conditional_edge_assign_nodes(self, state: OrchestratorState):
        if len(state["selected_nodes"]) == 0:
            return "synthesis"

        sends = []
        for node in state["selected_nodes"]:
            sends.append(
                Send(
                    node.name,
                    {
                        "node_key": node.name,
                        "custom_prompt": node.prompt,
                    },
                )
            )
        return sends

    def setup_workflow_chain(self):
        # Add nodes.
        self.workflow.add_node("orchestration", self.workflow_node_orchestration)
        self.workflow.add_node("synthesis", self.workflow_node_synthesis)
        for node in self.nodes.keys():
            self.workflow.add_node(node, self.workflow_node_call_node)
        self.add_memory_summarization_nodes()

        # Add edges.
        self.workflow.add_edge(START, "orchestration")
        self.workflow.add_conditional_edges(
            "orchestration",
            self.workflow_conditional_edge_assign_nodes,
            [*self.nodes.keys(), "synthesis"],
        )
        for node in self.nodes.keys():
            self.workflow.add_edge(node, "synthesis")
        self.add_memory_summarization_edges("synthesis", END)

        super().setup_workflow_chain()
