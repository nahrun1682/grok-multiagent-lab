import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.stream_parser import format_event_for_display, now_iso
from app.models import StreamEvent


def test_now_iso_format():
    ts = now_iso()
    assert "T" in ts
    assert ts.endswith("+00:00")


def test_format_event_content_delta():
    event = StreamEvent(
        timestamp="2026-01-01T00:00:00+00:00",
        event_type="content_delta",
        data={"content": "Hello"},
    )
    output = format_event_for_display(event)
    assert "content_delta" in output
    assert "Hello" in output


def test_format_event_thinking():
    event = StreamEvent(
        timestamp="2026-01-01T00:00:00+00:00",
        event_type="thinking",
        data={"reasoning_tokens": 512},
    )
    output = format_event_for_display(event)
    assert "thinking" in output
    assert "512" in output


def test_format_event_usage():
    event = StreamEvent(
        timestamp="2026-01-01T00:00:00+00:00",
        event_type="usage",
        data={
            "prompt_tokens": 100,
            "completion_tokens": 200,
            "reasoning_tokens": 50,
            "total_tokens": 350,
        },
    )
    output = format_event_for_display(event)
    assert "usage" in output
    assert "350" in output


def test_format_event_error():
    event = StreamEvent(
        timestamp="2026-01-01T00:00:00+00:00",
        event_type="error",
        data={"error": "API key missing"},
    )
    output = format_event_for_display(event)
    assert "error" in output
    assert "API key missing" in output


if __name__ == "__main__":
    test_now_iso_format()
    test_format_event_content_delta()
    test_format_event_thinking()
    test_format_event_usage()
    test_format_event_error()
    print("All tests passed.")
