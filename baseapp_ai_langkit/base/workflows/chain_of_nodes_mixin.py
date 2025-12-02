from abc import ABC, abstractmethod

from langgraph.graph import END, START

from baseapp_ai_langkit.base.interfaces.llm_node import LLMNodeInterface


class ChainOfNodesMixin(ABC):
    nodes: dict[str, LLMNodeInterface]

    def setup_chain_of_nodes(self):
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

    @abstractmethod
    def invoke_node(self, node: LLMNodeInterface):
        pass
