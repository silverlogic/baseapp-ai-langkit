from unittest.mock import patch

from django.test import TestCase

from baseapp_ai_langkit.base.agents.tests.factories import LLMFactory
from baseapp_ai_langkit.base.interfaces.base_runner import BaseRunnerInterface
from baseapp_ai_langkit.base.interfaces.llm_node import LLMNodeInterface
from baseapp_ai_langkit.base.prompt_schemas.tests.factories import (
    BasePromptSchemaFactory,
)
from baseapp_ai_langkit.runners.tests.factories import (
    LLMRunnerFactory,
    LLMRunnerNodeFactory,
    LLMRunnerNodeStateModifierFactory,
    LLMRunnerNodeUsagePromptFactory,
)


class MockedRunner(BaseRunnerInterface):
    def run(self) -> str:
        pass


class TestBaseRunnerInterface(TestCase):
    def test_base_runner_get_nodes_without_db_records(self):
        MockedNode = self._get_mocked_node()
        MockedNode.state_modifier_schema = BasePromptSchemaFactory()
        MockedNode.usage_prompt_schema = BasePromptSchemaFactory()
        MockedRunner.nodes = {
            "mock_node": MockedNode,
        }

        runner = MockedRunner()
        nodes = runner.get_nodes(llm=LLMFactory(), config={})

        self.assertIsInstance(nodes["mock_node"], MockedNode)
        self.assertEqual(nodes["mock_node"].state_modifier_schema, MockedNode.state_modifier_schema)
        self.assertEqual(nodes["mock_node"].usage_prompt_schema, MockedNode.usage_prompt_schema)

    def test_base_runner_get_nodes_with_empty_db_records(self):
        MockedNode = self._get_mocked_node()
        MockedNode.state_modifier_schema = BasePromptSchemaFactory()
        MockedNode.usage_prompt_schema = BasePromptSchemaFactory()
        MockedRunner.nodes = {
            "mock_node": MockedNode,
        }
        mock_runner_instance = LLMRunnerFactory(
            name=f"{MockedRunner.__module__}.{MockedRunner.__name__}"
        )
        mock_node = LLMRunnerNodeFactory(runner=mock_runner_instance, node="mock_node")
        LLMRunnerNodeUsagePromptFactory(runner_node=mock_node)
        LLMRunnerNodeStateModifierFactory(runner_node=mock_node, index=0)

        runner = MockedRunner()
        nodes = runner.get_nodes(llm=LLMFactory(), config={})

        self.assertIsInstance(nodes["mock_node"], MockedNode)
        self.assertEqual(nodes["mock_node"].state_modifier_schema, MockedNode.state_modifier_schema)
        self.assertEqual(nodes["mock_node"].usage_prompt_schema, MockedNode.usage_prompt_schema)

    @patch("baseapp_ai_langkit.runners.models.LLMRunner.get_nodes_dict")
    def test_base_runner_get_nodes_with_filled_db_records(self, mock_get_nodes_dict):
        MockedNode = self._get_mocked_node()
        MockedNode.state_modifier_schema = BasePromptSchemaFactory()
        MockedNode.usage_prompt_schema = BasePromptSchemaFactory()
        mock_get_nodes_dict.return_value = {
            "mock_node": MockedNode,
        }
        MockedRunner.nodes = {
            "mock_node": MockedNode,
        }
        mock_runner_instance = LLMRunnerFactory(
            name=f"{MockedRunner.__module__}.{MockedRunner.__name__}"
        )
        mock_node = LLMRunnerNodeFactory(runner=mock_runner_instance, node="mock_node")
        LLMRunnerNodeUsagePromptFactory(runner_node=mock_node, usage_prompt="custom usage prompt")
        LLMRunnerNodeStateModifierFactory(
            runner_node=mock_node, index=0, state_modifier="custom state modifier"
        )

        runner = MockedRunner()
        nodes = runner.get_nodes(llm=LLMFactory(), config={})

        self.assertIsInstance(nodes["mock_node"], MockedNode)
        self.assertEqual(nodes["mock_node"].usage_prompt_schema.prompt, "custom usage prompt")
        self.assertEqual(nodes["mock_node"].state_modifier_schema.prompt, "custom state modifier")

    @patch("baseapp_ai_langkit.runners.models.LLMRunner.get_nodes_dict")
    def test_base_runner_get_nodes_with_multiple_state_modifiers_db_records(
        self, mock_get_nodes_dict
    ):
        default_prompts = [BasePromptSchemaFactory(), BasePromptSchemaFactory()]
        MockedNode = self._get_mocked_node()
        MockedNode.usage_prompt_schema = BasePromptSchemaFactory()
        MockedNode.state_modifier_schema = default_prompts
        mock_get_nodes_dict.return_value = {
            "mock_node": MockedNode,
        }
        MockedRunner.nodes = {
            "mock_node": MockedNode,
        }
        mock_runner_instance = LLMRunnerFactory(
            name=f"{MockedRunner.__module__}.{MockedRunner.__name__}"
        )
        mock_node = LLMRunnerNodeFactory(runner=mock_runner_instance, node="mock_node")
        LLMRunnerNodeStateModifierFactory(
            runner_node=mock_node, index=0, state_modifier="custom state modifier 1"
        )

        runner = MockedRunner()
        nodes = runner.get_nodes(llm=LLMFactory(), config={})

        self.assertIsInstance(nodes["mock_node"], MockedNode)
        self.assertEqual(
            nodes["mock_node"].state_modifier_schema[0].prompt, "custom state modifier 1"
        )
        self.assertEqual(
            nodes["mock_node"].state_modifier_schema[1].prompt, default_prompts[1].prompt
        )

    @patch("baseapp_ai_langkit.runners.models.LLMRunner.get_nodes_dict")
    def test_base_runner_get_nodes_with_exception_in_maybe_override_prompt_schemas(
        self, mock_get_nodes_dict
    ):
        MockedNode = self._get_mocked_node()
        MockedNode.usage_prompt_schema = BasePromptSchemaFactory()
        default_state_modifier = [BasePromptSchemaFactory()]
        MockedNode.state_modifier_schema = default_state_modifier
        mock_get_nodes_dict.return_value = {
            "mock_node": MockedNode,
        }
        MockedRunner.nodes = {
            "mock_node": MockedNode,
        }

        mock_runner_instance = LLMRunnerFactory(
            name=f"{MockedRunner.__module__}.{MockedRunner.__name__}"
        )
        mock_node = LLMRunnerNodeFactory(runner=mock_runner_instance, node="mock_node")
        LLMRunnerNodeUsagePromptFactory(runner_node=mock_node, usage_prompt="custom usage prompt")
        # Because we have only one state modifier, having two records will raise an exception.
        LLMRunnerNodeStateModifierFactory(
            runner_node=mock_node, index=0, state_modifier="custom state modifier 1"
        )
        LLMRunnerNodeStateModifierFactory(
            runner_node=mock_node, index=1, state_modifier="custom state modifier 2"
        )

        runner = MockedRunner()
        nodes = runner.get_nodes(llm=LLMFactory(), config={})

        self.assertIsInstance(nodes["mock_node"], MockedNode)
        self.assertEqual(
            nodes["mock_node"].state_modifier_schema[0].prompt, default_state_modifier[0].prompt
        )

    def test_base_runner_instantiate_static_edge_node(self):
        default_state_modifier = [BasePromptSchemaFactory()]
        MockedNode = self._get_mocked_node()
        MockedNode.state_modifier_schema = default_state_modifier
        MockedRunner.edge_nodes = {
            "mock_node": MockedNode,
        }
        runner = MockedRunner()
        edge_node = runner.instantiate_edge_node("mock_node", llm=LLMFactory(), config={})
        self.assertIsInstance(edge_node, MockedNode)
        self.assertEqual(edge_node.state_modifier_schema, default_state_modifier)

    @patch("baseapp_ai_langkit.runners.models.LLMRunner.get_nodes_dict")
    def test_base_runner_instantiate_dynamic_edge_node(self, mock_get_nodes_dict):
        default_state_modifier = [BasePromptSchemaFactory()]
        MockedNode = self._get_mocked_node()
        MockedNode.state_modifier_schema = default_state_modifier
        mock_get_nodes_dict.return_value = {
            "mock_node": MockedNode,
        }
        MockedRunner.edge_nodes = {
            "mock_node": MockedNode,
        }
        mock_runner_instance = LLMRunnerFactory(
            name=f"{MockedRunner.__module__}.{MockedRunner.__name__}"
        )
        mock_node = LLMRunnerNodeFactory(runner=mock_runner_instance, node="mock_node")
        LLMRunnerNodeStateModifierFactory(
            runner_node=mock_node, index=0, state_modifier="custom state modifier 1"
        )

        runner = MockedRunner()
        edge_node = runner.instantiate_edge_node("mock_node", llm=LLMFactory(), config={})
        self.assertIsInstance(edge_node, MockedNode)
        self.assertEqual(edge_node.state_modifier_schema[0].prompt, "custom state modifier 1")

    def _get_mocked_node(self):
        class MockedNode(LLMNodeInterface):
            def invoke(self, *args, **kwargs):
                pass

        return MockedNode
