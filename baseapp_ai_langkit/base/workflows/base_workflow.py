from abc import ABC, abstractmethod
from typing import Any, Type

from langchain_core.runnables import RunnableConfig
from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph


class BaseWorkflow(ABC):
    """
    BaseWorkflow is a base class for all workflows in the LLM chat system.
    It provides a common interface for all workflows and ensures that they implement the necessary methods.

    Attributes:
        config (RunnableConfig): The configuration for the workflow.
        workflow (StateGraph): The workflow for the workflow.
        workflow_chain (CompiledStateGraph): The compiled workflow for the workflow.

    Args:
        config (RunnableConfig): The configuration for the workflow.

    Methods:
        setup_workflow() -> StateGraph: Setup the workflow.
        setup_workflow_chain() -> CompiledStateGraph: Setup the compiled workflow.
        get_state() -> Any: Get the state of the workflow.
        execute(*args, **kwargs) -> Any: Execute the workflow.
    """

    config: RunnableConfig
    workflow: StateGraph
    workflow_chain: CompiledStateGraph

    def __init__(
        self,
        config: RunnableConfig,
    ):
        self.config = config
        self.setup_workflow()
        self.setup_workflow_chain()

    def setup_workflow(self) -> StateGraph:
        self.workflow = StateGraph(self.state_graph_schema)

    @property
    @abstractmethod
    def state_graph_schema(self) -> Type[Any]:
        pass

    def setup_workflow_chain(self) -> CompiledStateGraph:
        self.workflow_chain = self.workflow.compile()

    def get_state(self):
        return self.workflow_chain.get_state(self.config)

    @abstractmethod
    def execute(self, *args, **kwargs):
        pass
