from unittest.mock import MagicMock, patch

from django.test import TestCase
from langchain_core.messages import AIMessage

from baseapp_ai_langkit.base.agents.tests.factories import LangGraphAgentFactory
from baseapp_ai_langkit.base.prompt_schemas.base_prompt_schema import BasePromptSchema
from baseapp_ai_langkit.tools.tests.factories import ToolFactory


class MockReactAgent(MagicMock):
    def invoke(self, *args, **kwargs) -> AIMessage:
        return {"messages": [AIMessage(content="Mocked content")]}


class TestLangGraphAgent(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.create_react_agent_patcher = patch(
            "baseapp_ai_langkit.base.agents.langgraph_agent.create_react_agent"
        )
        cls.mock_create_react_agent = cls.create_react_agent_patcher.start()
        cls.mock_create_react_agent.return_value = MockReactAgent()

    def setUp(self):
        self.tools = [ToolFactory()]
        self.state_modifier_schema = BasePromptSchema(
            description="Test description", prompt="Test prompt"
        )
        self.usage_prompt_schema = BasePromptSchema(
            description="Test description", prompt="Test prompt"
        )

    def test_base_langgraph_agent(self):
        agent = LangGraphAgentFactory(tools=self.tools)
        self.assertEqual(agent.tools, self.tools)
        self.assertIsNone(agent.checkpointer)
        self.assertFalse(agent.debug)

    def test_langgraph_agent_with_state_modifier(self):
        agent = LangGraphAgentFactory(
            tools=self.tools, state_modifier_schema=self.state_modifier_schema
        )
        self.assertEqual(agent.state_modifier_schema, self.state_modifier_schema)

    def test_langgraph_agent_with_usage_prompt_schema(self):
        agent = LangGraphAgentFactory(
            tools=self.tools, usage_prompt_schema=self.usage_prompt_schema
        )
        self.assertEqual(agent.usage_prompt_schema, self.usage_prompt_schema)

    def test_langgraph_agent_invoke(self):
        agent = LangGraphAgentFactory(tools=self.tools)
        messages = [MagicMock()]
        response = agent.invoke(messages)
        self.assertEqual(response.content, "Mocked content")

    def test_langgraph_agent_invoke_raises_exception(self):
        mock_agent = MagicMock()
        mock_agent.invoke.side_effect = Exception("Test error")
        self.mock_create_react_agent.return_value = mock_agent

        agent = LangGraphAgentFactory(tools=self.tools)
        messages = [MagicMock()]

        with self.assertRaises(Exception) as context:
            agent.invoke(messages)

        self.assertEqual(str(context.exception), "An unexpected error occurred. Please try again.")
