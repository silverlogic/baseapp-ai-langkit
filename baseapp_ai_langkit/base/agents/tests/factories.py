import factory
from langchain_core.language_models.fake_chat_models import FakeChatModel

from baseapp_ai_langkit.base.agents.langgraph_agent import LangGraphAgent


class LLMFactory(factory.Factory):
    class Meta:
        model = FakeChatModel


class LangGraphAgentFactory(factory.Factory):
    llm = factory.SubFactory(LLMFactory)
    config = {}

    class Meta:
        model = LangGraphAgent
