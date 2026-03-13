from datetime import datetime, timezone
from typing import Any
from app.models import StreamEvent


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_chunk(chunk: Any) -> StreamEvent:
    ts = now_iso()
    try:
        choice = chunk.choices[0] if chunk.choices else None
        delta = choice.delta if choice else None

        event_type = "unknown"
        data: dict[str, Any] = {}

        if delta:
            if delta.content:
                event_type = "content_delta"
                data = {"content": delta.content}
            elif hasattr(delta, "tool_calls") and delta.tool_calls:
                event_type = "tool_call_delta"
                tc = delta.tool_calls[0]
                data = {
                    "index": tc.index if hasattr(tc, "index") else "unknown",
                    "id": tc.id if tc.id else "unknown",
                    "function": {
                        "name": tc.function.name if tc.function and tc.function.name else "unknown",
                        "arguments": tc.function.arguments if tc.function and tc.function.arguments else "",
                    } if hasattr(tc, "function") else "unknown",
                }

        if chunk.usage:
            event_type = "usage"
            data = {
                "prompt_tokens": chunk.usage.prompt_tokens,
                "completion_tokens": chunk.usage.completion_tokens,
                "total_tokens": chunk.usage.total_tokens,
            }

        finish_reason = choice.finish_reason if choice else None
        if finish_reason:
            event_type = f"finish_{finish_reason}"
            data = {"finish_reason": finish_reason}

        raw_dict: Any = None
        try:
            raw_dict = chunk.model_dump()
        except Exception:
            raw_dict = str(chunk)

        return StreamEvent(
            timestamp=ts,
            event_type=event_type,
            data=data,
            raw=raw_dict,
        )

    except Exception as e:
        return StreamEvent(
            timestamp=ts,
            event_type="parse_error",
            data={"error": str(e)},
            raw=str(chunk),
        )


def format_event_for_display(event: StreamEvent) -> str:
    lines = [
        f"[{event.timestamp}] {event.event_type}",
    ]
    for k, v in event.data.items():
        lines.append(f"  {k}: {v}")
    return "\n".join(lines)
