from unittest.mock import MagicMock, patch

from django.test import TestCase

from baseapp_ai_langkit.runners.models import (
    LLMRunner,
    LLMRunnerNode,
    LLMRunnerNodeStateModifier,
    LLMRunnerNodeUsagePrompt,
)
from baseapp_ai_langkit.runners.tests.factories import (
    LLMRunnerFactory,
    LLMRunnerNodeFactory,
    LLMRunnerNodeStateModifierFactory,
    LLMRunnerNodeUsagePromptFactory,
)


class TestLLMRunner(TestCase):
    @patch("baseapp_ai_langkit.runners.registry.RunnerRegistry.get_all")
    def test_sync_runners_creates_llm_runner(self, mock_get_all):
        mock_runner_class = MagicMock()
        mock_runner_class.__module__ = "mock_module"
        mock_runner_class.__name__ = "MockRunner"
        mock_runner_class.nodes = {}
        mock_runner_class.get_available_nodes.return_value = mock_runner_class.nodes
        mock_get_all.return_value = [mock_runner_class]

        LLMRunner.sync_runners()

        llm_runner = LLMRunner.objects.get(name="mock_module.MockRunner")
        self.assertIsNotNone(llm_runner)

    @patch("baseapp_ai_langkit.runners.registry.RunnerRegistry.get_all")
    def test_sync_runners_creates_llm_runner_node(self, mock_get_all):
        mock_runner_class = MagicMock()
        mock_runner_class.__module__ = "mock_module"
        mock_runner_class.__name__ = "MockRunner"
        mock_runner_class.nodes = {"mock_node": MagicMock(state_modifier_schema=[1])}
        mock_runner_class.get_available_nodes.return_value = mock_runner_class.nodes
        mock_get_all.return_value = [mock_runner_class]

        LLMRunner.sync_runners()

        llm_runner = LLMRunner.objects.get(name="mock_module.MockRunner")
        llm_runner_node = LLMRunnerNode.objects.get(runner=llm_runner, node="mock_node")
        self.assertIsNotNone(llm_runner_node)

    @patch("baseapp_ai_langkit.runners.registry.RunnerRegistry.get_all")
    def test_sync_runners_creates_usage_prompt(self, mock_get_all):
        mock_runner_class = MagicMock()
        mock_runner_class.__module__ = "mock_module"
        mock_runner_class.__name__ = "MockRunner"
        mock_runner_class.nodes = {
            "mock_node": MagicMock(state_modifier_schema=[1], usage_prompt_schema=MagicMock())
        }
        mock_runner_class.get_available_nodes.return_value = mock_runner_class.nodes
        mock_get_all.return_value = [mock_runner_class]

        LLMRunner.sync_runners()

        llm_runner = LLMRunner.objects.get(name="mock_module.MockRunner")
        llm_runner_node = LLMRunnerNode.objects.get(runner=llm_runner, node="mock_node")
        usage_prompt = LLMRunnerNodeUsagePrompt.objects.get(runner_node=llm_runner_node)
        self.assertIsNotNone(usage_prompt)

    @patch("baseapp_ai_langkit.runners.registry.RunnerRegistry.get_all")
    def test_sync_runners_creates_state_modifier(self, mock_get_all):
        mock_runner_class = MagicMock()
        mock_runner_class.__module__ = "mock_module"
        mock_runner_class.__name__ = "MockRunner"
        mock_node_mock = MagicMock()
        mock_node_mock.get_static_state_modifier_list.return_value = [MagicMock()]
        mock_runner_class.nodes = {"mock_node": mock_node_mock}
        mock_runner_class.get_available_nodes.return_value = mock_runner_class.nodes
        mock_get_all.return_value = [mock_runner_class]

        LLMRunner.sync_runners()

        llm_runner = LLMRunner.objects.get(name="mock_module.MockRunner")
        llm_runner_node = LLMRunnerNode.objects.get(runner=llm_runner, node="mock_node")
        state_modifier = LLMRunnerNodeStateModifier.objects.get(
            runner_node=llm_runner_node, index=0
        )
        self.assertIsNotNone(state_modifier)

    @patch("baseapp_ai_langkit.runners.registry.RunnerRegistry.get_all")
    def test_sync_runners_creates_multiple_state_modifiers(self, mock_get_all):
        mock_runner_class = MagicMock()
        mock_runner_class.__module__ = "mock_module"
        mock_runner_class.__name__ = "MockRunner"
        mock_node_mock = MagicMock()
        mock_node_mock.get_static_state_modifier_list.return_value = [MagicMock(), MagicMock()]
        mock_runner_class.nodes = {"mock_node": mock_node_mock}
        mock_runner_class.get_available_nodes.return_value = mock_runner_class.nodes
        mock_get_all.return_value = [mock_runner_class]

        LLMRunner.sync_runners()

        llm_runner = LLMRunner.objects.get(name="mock_module.MockRunner")
        llm_runner_node = LLMRunnerNode.objects.get(runner=llm_runner, node="mock_node")
        state_modifiers = LLMRunnerNodeStateModifier.objects.filter(runner_node=llm_runner_node)
        self.assertEqual(len(state_modifiers), 2)
        self.assertEqual(state_modifiers[0].index, 0)
        self.assertEqual(state_modifiers[1].index, 1)

    def test_sync_runners_deletes_unused_runners(self):
        runner = LLMRunnerFactory()
        runner_node = LLMRunnerNodeFactory(runner=runner)
        usage_prompt = LLMRunnerNodeUsagePromptFactory(runner_node=runner_node)
        state_modifier = LLMRunnerNodeStateModifierFactory(runner_node=runner_node)

        LLMRunner.sync_runners()

        self.assertFalse(LLMRunner.objects.filter(id=runner.id).exists())
        self.assertFalse(LLMRunnerNode.objects.filter(id=runner_node.id).exists())
        self.assertFalse(LLMRunnerNodeUsagePrompt.objects.filter(id=usage_prompt.id).exists())
        self.assertFalse(LLMRunnerNodeStateModifier.objects.filter(id=state_modifier.id).exists())
