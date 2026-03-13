import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import MagicMock
from app.stream_parser import parse_chunk, format_event_for_display, now_iso


def test_now_iso_format():
    ts = now_iso()
    assert "T" in ts
    assert ts.endswith("+00:00")


def test_parse_chunk_content_delta():
    chunk = MagicMock()
    chunk.choices = [MagicMock()]
    chunk.choices[0].delta.content = "Hello"
    chunk.choices[0].delta.tool_calls = None
    chunk.choices[0].finish_reason = None
    chunk.usage = None
    chunk.model_dump.return_value = {}

    event = parse_chunk(chunk)
    assert event.event_type == "content_delta"
    assert event.data["content"] == "Hello"


def test_parse_chunk_usage():
    chunk = MagicMock()
    chunk.choices = []
    chunk.usage = MagicMock()
    chunk.usage.prompt_tokens = 10
    chunk.usage.completion_tokens = 20
    chunk.usage.total_tokens = 30
    chunk.model_dump.return_value = {}

    event = parse_chunk(chunk)
    assert event.event_type == "usage"
    assert event.data["total_tokens"] == 30


def test_parse_chunk_finish():
    chunk = MagicMock()
    chunk.choices = [MagicMock()]
    chunk.choices[0].delta.content = None
    chunk.choices[0].delta.tool_calls = None
    chunk.choices[0].finish_reason = "stop"
    chunk.usage = None
    chunk.model_dump.return_value = {}

    event = parse_chunk(chunk)
    assert event.event_type == "finish_stop"


def test_format_event_for_display():
    from app.models import StreamEvent
    event = StreamEvent(
        timestamp="2026-01-01T00:00:00+00:00",
        event_type="content_delta",
        data={"content": "test"},
    )
    output = format_event_for_display(event)
    assert "content_delta" in output
    assert "test" in output


if __name__ == "__main__":
    test_now_iso_format()
    test_parse_chunk_content_delta()
    test_parse_chunk_usage()
    test_parse_chunk_finish()
    test_format_event_for_display()
    print("All tests passed.")
