"""CLI entry point for the Message Notification Router.

Usage:
    python code/main.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from router.data_loader import build_message_context, load_dataset  # noqa: E402


def main() -> None:
    ds = load_dataset()

    print("Loaded dataset:")
    print(f"  messages: {len(ds.messages)}")
    print(f"  sample_messages: {len(ds.sample_messages)}")
    print(f"  users: {len(ds.users)}")
    print(f"  groups: {len(ds.groups)}")
    print(f"  group_members: {len(ds.group_members)}")
    print(f"  business_accounts: {len(ds.business_accounts)}")
    print(f"  user_business_history: {len(ds.user_business_history)}")
    print(f"  message_history: {len(ds.message_history)}")
    print(f"  message_events: {len(ds.message_events)}")
    print(f"  images: {len(ds.images)}")
    print(f"  voice_notes: {len(ds.voice_notes)}")
    print(f"  daily_notification_summary: {len(ds.daily_notification_summary)}")

    sample = ds.messages[0]
    ctx = build_message_context(ds, sample)
    print(f"\nSample joined context for {sample['message_id']}:")
    print(f"  user: {ctx.user}")
    print(f"  group: {ctx.group}")
    print(f"  business: {ctx.business}")
    print(f"  user_history size: {len(ctx.user_history)}")


if __name__ == "__main__":
    main()