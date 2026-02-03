import psycopg
from django.conf import settings
from django.db import DEFAULT_DB_ALIAS
from langgraph.checkpoint.postgres import PostgresSaver


class CompatiblePostgresSaver(PostgresSaver):
    """
    A compatibility wrapper for PostgresSaver that handles both old and new checkpoint formats.

    Old checkpoints (v2) don't have 'channel_values' field in the database row, while new
    checkpoints (v4) require it. This wrapper ensures backward compatibility by providing
    a default empty dict/list for missing 'channel_values' when loading old checkpoints.
    """

    def _load_checkpoint_tuple(self, value):
        """
        Override to handle backward compatibility with old checkpoint formats.

        The parent method calls _load_blobs(value["channel_values"]) which fails if
        channel_values is None. We ensure it's never None before calling the parent.
        """
        # Ensure channel_values in the row is never None (compatibility with old checkpoints)
        if value.get("channel_values") is None:
            value["channel_values"] = []

        # Ensure checkpoint dict has channel_values field
        checkpoint = value.get("checkpoint", {})
        if isinstance(checkpoint, dict):
            if "channel_values" not in checkpoint or checkpoint.get("channel_values") is None:
                checkpoint = {**checkpoint, "channel_values": {}}
                value["checkpoint"] = checkpoint

        # Call parent method with patched value
        return super()._load_checkpoint_tuple(value)


class LangGraphCheckpointer:
    db_alias: str
    checkpointer: PostgresSaver

    def __init__(self, db_alias=DEFAULT_DB_ALIAS):
        """
        Initialize the LangGraph checkpointer using psycopg.

        :Args
            db_alias: The alias of the database in Django's settings.
        """
        self.db_alias = db_alias

    def setup(self):
        """Set up the PostgresSaver using psycopg's connection."""
        # Use CompatiblePostgresSaver instead of PostgresSaver for backward compatibility
        self.checkpointer = CompatiblePostgresSaver(self._get_connection())
        self.checkpointer.setup()

    def get_checkpointer(self) -> PostgresSaver:
        if not self.checkpointer:
            raise RuntimeError("Call `setup()` before getting the checkpointer.")
        return self.checkpointer

    def _get_connection(self):
        db_settings = settings.DATABASES[self.db_alias]

        dsn = (
            f"postgresql://{db_settings['USER']}:{db_settings['PASSWORD']}"
            f"@{db_settings['HOST']}:{db_settings['PORT']}/{db_settings['NAME']}"
        )

        return psycopg.connect(dsn, autocommit=True)
