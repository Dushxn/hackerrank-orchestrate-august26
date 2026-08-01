"""Phase 1 tests: data loading, indexing, and joined message context."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "code"))

from router.data_loader import build_message_context, load_dataset  # noqa: E402

DS = load_dataset()
SAMPLES_BY_ID = {r["message_id"]: r for r in DS.sample_messages}


def test_row_counts_match_actual_csv_parsing() -> None:
    # These counts were verified by loading with a real CSV parser (which
    # correctly handles embedded newlines in quoted message_text fields) —
    # a naive `wc -l` line count over-counts because of those newlines.
    assert len(DS.messages) == 110
    assert len(DS.sample_messages) == 30
    assert len(DS.users) == 54
    assert len(DS.groups) == 23
    assert len(DS.group_members) == 401
    assert len(DS.business_accounts) == 110
    assert len(DS.user_business_history) == 106
    assert len(DS.message_history) == 412
    assert len(DS.message_events) == 412
    assert len(DS.images) == 20
    assert len(DS.voice_notes) == 13


def test_group_message_context_joins_group_and_member() -> None:
    msg = SAMPLES_BY_ID["sample_msg_001"]
    ctx = build_message_context(DS, msg)

    assert ctx.user is not None and ctx.user["user_id"] == "u_011"
    assert ctx.group is not None
    assert ctx.group["group_name"] == "Green Acres Society Notices"
    assert ctx.business is None
    assert ctx.group_member is not None
    assert ctx.group_member["user_id"] == "u_011"
    assert ctx.group_member["group_id"] == "group_002"


def test_business_message_context_joins_business_and_history() -> None:
    msg = SAMPLES_BY_ID["sample_msg_004"]
    ctx = build_message_context(DS, msg)

    assert ctx.business is not None
    assert ctx.business["business_id"] == "business_001"
    assert ctx.business["display_name"] == "Amazon India"
    assert ctx.group is None
    # user_business_history join should resolve for a known (user, business) pair
    assert ctx.user_business is not None
    assert ctx.user_business["business_id"] == "business_001"


def test_personal_message_context_has_sender_and_no_group_or_business() -> None:
    msg = SAMPLES_BY_ID["sample_msg_049"]
    ctx = build_message_context(DS, msg)

    assert ctx.group is None
    assert ctx.business is None
    assert ctx.group_member is None
    assert ctx.user_business is None
    # sender history is looked up by sender_user_id, must not crash
    assert isinstance(ctx.sender_history, list)


def test_blank_optional_fields_never_crash() -> None:
    # A synthetic row exercising every "blank" branch (new sender with
    # nothing in group/business/history tables).
    synthetic = {
        "message_id": "synthetic_1",
        "user_id": "u_001",
        "conversation_type": "personal",
        "group_id": "",
        "business_id": "",
        "sender_user_id": "",
        "created_at": "2026-07-31 00:00",
        "message_text": "hello",
        "media_type": "",
        "media_id": "",
        "forwarded_count": "0",
    }
    ctx = build_message_context(DS, synthetic)
    assert ctx.group is None
    assert ctx.business is None
    assert ctx.group_member is None
    assert ctx.user_business is None
    assert ctx.image is None
    assert ctx.voice_note is None
    assert ctx.sender_history == []


def test_every_message_row_produces_context_without_error() -> None:
    # Integration-style smoke test: every real row in messages.csv must be
    # joinable without raising, since Phase 6+ will iterate over all of them.
    for msg in DS.messages:
        ctx = build_message_context(DS, msg)
        assert ctx.user is not None, f"missing user for {msg['message_id']}"