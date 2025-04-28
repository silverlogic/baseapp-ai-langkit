from typing import Type

from typing_extensions import TypedDict

from baseapp_ai_langkit.base.interfaces.llm_node import LLMNodeInterface
from baseapp_ai_langkit.base.workflows.base_workflow import BaseWorkflow
from baseapp_ai_langkit.base.workflows.chain_of_nodes_mixin import ChainOfNodesMixin


class OutputState(TypedDict):
    output: str


class ExecutorWorkflow(ChainOfNodesMixin, BaseWorkflow):
    """
    ExecutorWorkflow is a workflow that executes a list of nodes.
    It's designed to be executed by executors (workers or agents designed to have only one interaction - no memory).

    Args:
        nodes (dict[str, LLMNodeInterface]): A dictionary of nodes to execute.
        state_schema (Type[OutputState]): The state schema for the workflow.
    """

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
        self.setup_chain_of_nodes()
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
