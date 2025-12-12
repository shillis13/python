import pytest

from ai_utils.chat_processing.chat_chunker import chunk_chat


def test_single_chunk_for_small_chat():
    messages = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi there"},
    ]

    chunks = chunk_chat(messages, target_size=100)

    assert len(chunks) == 1
    assert chunks[0] == messages


def test_break_before_user_when_near_limit():
    # First assistant response is close to the threshold; next user prompt
    # should start a new chunk to keep the assistant response intact.
    messages = [
        {"role": "assistant", "content": "a" * 75},
        {"role": "user", "content": "follow up?"},
        {"role": "assistant", "content": "sure"},
    ]

    chunks = chunk_chat(messages, target_size=80, size_unit="chars")

    assert len(chunks) == 2
    assert [m["role"] for m in chunks[0]] == ["assistant"]
    assert [m["role"] for m in chunks[1]] == ["user", "assistant"]


def test_oversized_single_message_isolated():
    messages = [
        {"role": "assistant", "content": "a" * 120},
        {"role": "user", "content": "small"},
    ]

    chunks = chunk_chat(messages, target_size=50, size_unit="chars")

    assert len(chunks[0]) == 1
    assert chunks[0][0]["content"] == "a" * 120


def test_overlap_includes_previous_tail():
    messages = [
        {"role": "user", "content": "q1" * 10},
        {"role": "assistant", "content": "a1" * 10},
        {"role": "user", "content": "q2" * 10},
    ]

    chunks = chunk_chat(messages, target_size=60, size_unit="chars", overlap=1)

    assert len(chunks) == 2
    # Overlap should bring the last message from chunk 1 into chunk 2.
    assert chunks[1][0]["content"] == "a1" * 10
    assert [m["role"] for m in chunks[1]] == ["assistant", "user"]


def test_empty_messages_returns_empty_list():
    assert chunk_chat([], target_size=10) == []
