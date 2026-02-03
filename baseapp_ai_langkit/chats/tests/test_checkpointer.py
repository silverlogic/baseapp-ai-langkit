from unittest.mock import MagicMock, patch

from django.test import TestCase

from baseapp_ai_langkit.chats.checkpointer import CompatiblePostgresSaver


class TestCompatiblePostgresSaver(TestCase):
    def setUp(self):
        self.mock_connection = MagicMock()
        self.saver = CompatiblePostgresSaver(self.mock_connection)

    @patch("baseapp_ai_langkit.chats.checkpointer.PostgresSaver._load_checkpoint_tuple")
    def test_load_checkpoint_tuple_with_old_format_missing_channel_values(self, mock_parent):
        # Simulate old checkpoint format (v2.0.8) - missing channel_values
        value = {
            "checkpoint": {
                "ts": "2024-01-01T00:00:00",
                "channel_versions": {},
            }
        }
        expected_result = MagicMock()
        mock_parent.return_value = expected_result

        result = self.saver._load_checkpoint_tuple(value)

        # Verify channel_values was added to the row
        self.assertEqual(value["channel_values"], [])
        # Verify parent method was called with patched value
        mock_parent.assert_called_once_with(value)
        self.assertEqual(result, expected_result)

    @patch("baseapp_ai_langkit.chats.checkpointer.PostgresSaver._load_checkpoint_tuple")
    def test_load_checkpoint_tuple_with_old_format_none_channel_values(self, mock_parent):
        # Simulate old checkpoint format (v2.0.8) - channel_values is None
        value = {
            "channel_values": None,
            "checkpoint": {
                "ts": "2024-01-01T00:00:00",
                "channel_versions": {},
            },
        }
        expected_result = MagicMock()
        mock_parent.return_value = expected_result

        result = self.saver._load_checkpoint_tuple(value)

        # Verify channel_values was changed from None to []
        self.assertEqual(value["channel_values"], [])
        # Verify parent method was called with patched value
        mock_parent.assert_called_once_with(value)
        self.assertEqual(result, expected_result)

    @patch("baseapp_ai_langkit.chats.checkpointer.PostgresSaver._load_checkpoint_tuple")
    def test_load_checkpoint_tuple_with_old_format_missing_channel_values_in_checkpoint(
        self, mock_parent
    ):
        # Simulate old checkpoint format - missing channel_values in checkpoint dict
        value = {
            "channel_values": [],
            "checkpoint": {
                "ts": "2024-01-01T00:00:00",
                "channel_versions": {},
            },
        }
        expected_result = MagicMock()
        mock_parent.return_value = expected_result

        result = self.saver._load_checkpoint_tuple(value)

        # Verify channel_values was added to checkpoint dict
        self.assertIn("channel_values", value["checkpoint"])
        self.assertEqual(value["checkpoint"]["channel_values"], {})
        # Verify parent method was called with patched value
        mock_parent.assert_called_once_with(value)
        self.assertEqual(result, expected_result)

    @patch("baseapp_ai_langkit.chats.checkpointer.PostgresSaver._load_checkpoint_tuple")
    def test_load_checkpoint_tuple_with_old_format_none_channel_values_in_checkpoint(
        self, mock_parent
    ):
        # Simulate old checkpoint format - channel_values is None in checkpoint dict
        value = {
            "channel_values": [],
            "checkpoint": {
                "ts": "2024-01-01T00:00:00",
                "channel_versions": {},
                "channel_values": None,
            },
        }
        expected_result = MagicMock()
        mock_parent.return_value = expected_result

        result = self.saver._load_checkpoint_tuple(value)

        # Verify channel_values was changed from None to {}
        self.assertEqual(value["checkpoint"]["channel_values"], {})
        # Verify parent method was called with patched value
        mock_parent.assert_called_once_with(value)
        self.assertEqual(result, expected_result)

    @patch("baseapp_ai_langkit.chats.checkpointer.PostgresSaver._load_checkpoint_tuple")
    def test_load_checkpoint_tuple_with_new_format(self, mock_parent):
        # Simulate new checkpoint format (v2.0.25) - channel_values present
        value = {
            "channel_values": [{"key": "value"}],
            "checkpoint": {
                "ts": "2024-01-01T00:00:00",
                "channel_versions": {},
                "channel_values": {"some": "data"},
            },
        }
        expected_result = MagicMock()
        mock_parent.return_value = expected_result

        result = self.saver._load_checkpoint_tuple(value)

        # Verify values were not modified (already correct)
        self.assertEqual(value["channel_values"], [{"key": "value"}])
        self.assertEqual(value["checkpoint"]["channel_values"], {"some": "data"})
        # Verify parent method was called with original value
        mock_parent.assert_called_once_with(value)
        self.assertEqual(result, expected_result)

    @patch("baseapp_ai_langkit.chats.checkpointer.PostgresSaver._load_checkpoint_tuple")
    def test_load_checkpoint_tuple_with_missing_checkpoint_dict(self, mock_parent):
        # Simulate checkpoint with missing checkpoint dict
        value = {
            "channel_values": None,
        }
        expected_result = MagicMock()
        mock_parent.return_value = expected_result

        result = self.saver._load_checkpoint_tuple(value)

        # Verify channel_values was added to the row
        self.assertEqual(value["channel_values"], [])
        # Verify checkpoint dict was created
        self.assertIn("checkpoint", value)
        self.assertEqual(value["checkpoint"], {"channel_values": {}})
        # Verify parent method was called with patched value
        mock_parent.assert_called_once_with(value)
        self.assertEqual(result, expected_result)

    @patch("baseapp_ai_langkit.chats.checkpointer.PostgresSaver._load_checkpoint_tuple")
    def test_load_checkpoint_tuple_with_non_dict_checkpoint(self, mock_parent):
        # Simulate checkpoint where checkpoint is not a dict
        value = {
            "channel_values": [],
            "checkpoint": "not-a-dict",
        }
        expected_result = MagicMock()
        mock_parent.return_value = expected_result

        result = self.saver._load_checkpoint_tuple(value)

        # Verify channel_values was set in row
        self.assertEqual(value["channel_values"], [])
        # Verify checkpoint was not modified (not a dict, so we skip it)
        self.assertEqual(value["checkpoint"], "not-a-dict")
        # Verify parent method was called
        mock_parent.assert_called_once_with(value)
        self.assertEqual(result, expected_result)

    @patch("baseapp_ai_langkit.chats.checkpointer.PostgresSaver._load_checkpoint_tuple")
    def test_load_checkpoint_tuple_complete_old_format(self, mock_parent):
        # Simulate complete old checkpoint format - missing channel_values in both places
        value = {
            "checkpoint": {
                "ts": "2024-01-01T00:00:00",
                "channel_versions": {},
            },
        }
        expected_result = MagicMock()
        mock_parent.return_value = expected_result

        result = self.saver._load_checkpoint_tuple(value)

        # Verify both channel_values were added
        self.assertEqual(value["channel_values"], [])
        self.assertIn("channel_values", value["checkpoint"])
        self.assertEqual(value["checkpoint"]["channel_values"], {})
        # Verify parent method was called with patched value
        mock_parent.assert_called_once_with(value)
        self.assertEqual(result, expected_result)
