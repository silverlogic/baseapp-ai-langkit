from unittest.mock import MagicMock, patch

import pytest
from langchain.schema import AIMessage

from baseapp_ai_langkit.base.agents.tests.factories import DefaultAgentFactory

pytestmark = pytest.mark.django_db


@patch("baseapp_ai_langkit.base.agents.base_agent.create_react_agent")
@patch("baseapp_ai_langkit.base.agents.base_agent.AgentExecutor")
def test_default_agent_initialize_agent(mock_agent_executor, mock_create_agent):
    fake_agent = MagicMock()
    fake_executor = MagicMock()
    mock_create_agent.return_value = fake_agent
    mock_agent_executor.return_value = fake_executor

    agent = DefaultAgentFactory()

    mock_create_agent.assert_called_once_with(
        tools=agent.tools,
        llm=agent.llm,
        prompt=agent.prompt_template,
    )
    mock_agent_executor.assert_called_once_with(
        agent=fake_agent,
        tools=agent.tools,
        verbose=True,
        handle_parsing_errors=True,
        max_iterations=5,
        stream_runnable=False,
    )
    assert agent.agent_executor == fake_executor


@patch("baseapp_ai_langkit.base.agents.base_agent.create_react_agent")
@patch("baseapp_ai_langkit.base.agents.base_agent.AgentExecutor")
def test_default_agent_invoke(mock_agent_executor, mock_create_agent):
    fake_agent = MagicMock()
    fake_executor = MagicMock()
    mock_create_agent.return_value = fake_agent
    fake_executor.invoke.return_value = {"output": "Hello world!"}
    mock_agent_executor.return_value = fake_executor

    agent = DefaultAgentFactory()

    response = agent.invoke("Hi!")

    assert isinstance(response, AIMessage)
    assert response.content == "Hello world!"
    fake_executor.invoke.assert_called_once_with({"input": "Hi!", "chat_history": []})
