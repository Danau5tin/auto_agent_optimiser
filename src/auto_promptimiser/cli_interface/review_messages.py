"""
Utility script to review the message history from an optimisation run.

Usage:
    python review_messages.py [run_id]

If no run_id is provided, shows all available runs.
"""
import asyncio
import sys
import json
from pathlib import Path
from uuid import UUID

from auto_promptimiser.storage.message_storage_nosql import NoSQLMessageStorage



async def list_all_runs(storage: NoSQLMessageStorage):
    """List all available runs in the message history."""
    docs = storage.table.all()
    if not docs:
        print("No message histories found.")
        return

    print("\nAvailable runs:")
    print("-" * 80)
    for doc in docs:
        run_id = doc['optimise_run_id']
        message_count = len(doc['messages'])
        print(f"Run ID: {run_id}")
        print(f"  Messages: {message_count}")
        print()


async def display_messages(storage: NoSQLMessageStorage, run_id: UUID):
    """Display the messages for a specific run."""
    messages = await storage.get_messages(run_id)

    if messages is None:
        print(f"No messages found for run ID: {run_id}")
        return

    print(f"\nMessage history for run: {run_id}")
    print("=" * 80)

    for i, msg in enumerate(messages, 1):
        role = msg.get('role', 'unknown')
        content = msg.get('content', '')

        print(f"\n[{i}] Role: {role.upper()}")
        print("-" * 80)

        # Truncate very long messages for readability
        if len(content) > 2000:
            print(content[:2000])
            print(f"\n... (truncated, {len(content) - 2000} more characters)")
        else:
            print(content)
        print()


async def main():
    script_dir = Path(__file__).parent
    message_history_path = script_dir / "message_history.json"

    if not message_history_path.exists():
        print(f"No message history found at: {message_history_path}")
        return

    storage = NoSQLMessageStorage(db_path=str(message_history_path))

    try:
        if len(sys.argv) > 1:
            # Display specific run
            run_id_str = sys.argv[1]
            try:
                run_id = UUID(run_id_str)
                await display_messages(storage, run_id)
            except ValueError:
                print(f"Invalid UUID: {run_id_str}")
        else:
            # List all runs
            await list_all_runs(storage)
            print("\nTo view messages for a specific run:")
            print("  python review_messages.py <run_id>")
    finally:
        storage.close()


if __name__ == "__main__":
    asyncio.run(main())
