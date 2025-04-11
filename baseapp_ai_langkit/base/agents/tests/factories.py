import factory
from langchain.prompts import PromptTemplate
from langchain_core.language_models.fake_chat_models import FakeChatModel

from baseapp_ai_langkit.base.agents.base_agent import DefaultAgent
from baseapp_ai_langkit.base.agents.langgraph_agent import LangGraphAgent
from baseapp_ai_langkit.tools.tests.factories import DefaultToolFactory, ToolFactory


class LLMFactory(factory.Factory):
    class Meta:
        model = FakeChatModel


class DefaultAgentFactory(factory.Factory):
    llm = factory.SubFactory(LLMFactory)
    prompt_template = factory.LazyAttribute(
        lambda _: PromptTemplate(template="Answer the question: {input}")
    )
    tools = factory.List([factory.SubFactory(DefaultToolFactory)])
    memory = None

    class Meta:
        model = DefaultAgent


class LangGraphAgentFactory(factory.Factory):
    llm = factory.SubFactory(LLMFactory)
    config = {}
    tools = factory.List([factory.SubFactory(ToolFactory)])

    class Meta:
        model = LangGraphAgent
