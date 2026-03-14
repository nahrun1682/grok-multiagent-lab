from datetime import datetime, timezone
from typing import Any
from app.models import StreamEvent


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def format_event_for_display(event: StreamEvent) -> str:
    lines = [f"[{event.timestamp}] {event.event_type}"]
    for k, v in event.data.items():
        lines.append(f"  {k}: {v}")
    return "\n".join(lines)
