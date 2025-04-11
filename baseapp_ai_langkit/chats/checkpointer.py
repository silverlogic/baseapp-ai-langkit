import psycopg
from django.conf import settings
from django.db import DEFAULT_DB_ALIAS
from langgraph.checkpoint.postgres import PostgresSaver


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
        self.checkpointer = PostgresSaver(self._get_connection())
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
