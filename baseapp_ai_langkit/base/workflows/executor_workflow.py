from typing import Type

from langgraph.graph import END, START
from typing_extensions import TypedDict

from baseapp_ai_langkit.base.interfaces.llm_node import LLMNodeInterface
from baseapp_ai_langkit.base.workflows.base_workflow import BaseWorkflow


class OutputState(TypedDict):
    output: str


class ExecutorWorkflow(BaseWorkflow):
    """
    ExecutorWorkflow is a workflow that executes a list of nodes.
    It's designed to be executed by executors (workers or agents designed to have only one interaction - no memory).

    Args:
        nodes (dict[str, LLMNodeInterface]): A dictionary of nodes to execute.
        state_schema (Type[OutputState]): The state schema for the workflow.
    """

    nodes: dict[str, LLMNodeInterface]

    def __init__(
        self,
        nodes: dict[str, LLMNodeInterface],
        state_schema: Type[OutputState] = OutputState,
        *args,
        **kwargs,
    ):
        self.nodes = nodes
        self.state_schema = state_schema
        super().__init__(*args, **kwargs)

    @property
    def state_graph_schema(self) -> Type[OutputState]:
        return self.state_schema

    def setup_workflow_chain(self):
        node_slugs = list(self.nodes.keys())

        for slug, node in self.nodes.items():
            self.workflow.add_node(slug, self.invoke_node(node))

        for i, slug in enumerate(node_slugs):
            if i == 0:
                self.workflow.add_edge(START, slug)
            elif i == len(node_slugs) - 1:
                self.workflow.add_edge(node_slugs[i - 1], slug)
                self.workflow.add_edge(slug, END)
            else:
                self.workflow.add_edge(node_slugs[i - 1], slug)

        super().setup_workflow_chain()

    def invoke_node(self, node: LLMNodeInterface):
        def format_output(state: OutputState):
            response = node.invoke([], state)
            return {"output": response.content}

        return format_output

    def execute(self, state: dict = {}):
        workflow_state = {"output": ""}
        workflow_state.update(state)
        return self.workflow_chain.invoke(workflow_state, self.config)
