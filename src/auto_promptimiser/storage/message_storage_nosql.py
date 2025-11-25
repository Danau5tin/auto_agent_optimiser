from uuid import UUID
from pathlib import Path
from auto_promptimiser.core.base_message_storage import BaseMessageStorage
from tinydb import TinyDB, Query


class NoSQLMessageStorage(BaseMessageStorage):
    """TinyDB-based NoSQL implementation of message history storage."""

    def __init__(self, db_path: str = "message_history.json"):
        """
        Initialize the NoSQL message storage.

        Args:
            db_path: Path to the TinyDB JSON file. Defaults to "message_history.json"
        """
        self.db_path = Path(db_path)
        self.db = TinyDB(self.db_path)
        self.table = self.db.table('message_history')

    async def store_messages(
        self,
        run_id: UUID,
        messages: list[dict]
    ) -> None:
        """Store message history for a specific run."""
        document = {
            'optimise_run_id': str(run_id),
            'messages': messages
        }

        MessageQuery = Query()
        existing = self.table.search(MessageQuery.optimise_run_id == str(run_id))

        if existing:
            self.table.update(
                document,
                MessageQuery.optimise_run_id == str(run_id)
            )
        else:
            self.table.insert(document)

    async def get_messages(self, run_id: UUID) -> list[dict] | None:
        """Retrieve message history for a given run. Returns None if not found."""
        MessageQuery = Query()
        documents = self.table.search(MessageQuery.optimise_run_id == str(run_id))

        if not documents:
            return None

        return documents[0]['messages']

    def close(self) -> None:
        """Close the database connection."""
        self.db.close()

    def clear_run(self, run_id: UUID) -> None:
        """Delete message history for a specific run."""
        MessageQuery = Query()
        self.table.remove(MessageQuery.optimise_run_id == str(run_id))

    def clear_all(self) -> None:
        """Delete all stored message histories."""
        self.table.truncate()
