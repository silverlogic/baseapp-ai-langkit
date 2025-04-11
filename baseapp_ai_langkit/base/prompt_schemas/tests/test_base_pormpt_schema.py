from django.test import TestCase

from baseapp_ai_langkit.base.prompt_schemas.base_prompt_schema import BasePromptSchema


class TestBasePromptSchema(TestCase):
    def test_prompt_schema_initialization(self):
        schema = BasePromptSchema(
            description="Test description",
            prompt="Test prompt with {var1} and {var2}",
            required_placeholders=["var1", "var2"],
            placeholders_data={"var1": "value1", "var2": "value2"},
        )
        self.assertEqual(schema.description, "Test description")
        self.assertEqual(schema.prompt, "Test prompt with {var1} and {var2}")
        self.assertEqual(schema.required_placeholders, ["var1", "var2"])
        self.assertEqual(schema.placeholders_data, {"var1": "value1", "var2": "value2"})

    def test_validate_with_valid_placeholders(self):
        schema = BasePromptSchema(
            description="Test", prompt="Test {var1} {var2}", required_placeholders=["var1", "var2"]
        )
        self.assertTrue(schema.validate())

    def test_validate_with_missing_placeholders(self):
        schema = BasePromptSchema(
            description="Test", prompt="Test {var1}", required_placeholders=["var1", "var2"]
        )
        self.assertFalse(schema.validate())

    def test_format_with_placeholders(self):
        schema = BasePromptSchema(
            description="Test", prompt="Hello {name}!", placeholders_data={"name": "World"}
        )
        self.assertEqual(schema.format(), "Hello World!")

    def test_get_langgraph_message_without_conditional(self):
        from langchain_core.messages import HumanMessage

        schema = BasePromptSchema(
            description="Test", prompt="Hello {name}!", placeholders_data={"name": "World"}
        )
        message = schema.get_langgraph_message(HumanMessage)
        self.assertIsNotNone(message)
        self.assertEqual(message.content, "Hello World!")

    def test_get_langgraph_message_with_conditional_true(self):
        from langchain_core.messages import HumanMessage

        schema = BasePromptSchema(
            description="Test",
            prompt="Hello {name}!",
            placeholders_data={"name": "World"},
            conditional_rule=lambda data: True,
        )
        message = schema.get_langgraph_message(HumanMessage)
        self.assertIsNotNone(message)
        self.assertEqual(message.content, "Hello World!")

    def test_get_langgraph_message_with_conditional_false(self):
        from langchain_core.messages import HumanMessage

        schema = BasePromptSchema(
            description="Test",
            prompt="Hello {name}!",
            placeholders_data={"name": "World"},
            conditional_rule=lambda data: False,
        )
        message = schema.get_langgraph_message(HumanMessage)
        self.assertIsNone(message)
