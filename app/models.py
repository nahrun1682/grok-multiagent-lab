from dataclasses import dataclass, field
from typing import Any


@dataclass
class StreamEvent:
    timestamp: str
    event_type: str
    data: dict[str, Any]
    raw: Any = None


@dataclass
class SessionResult:
    events: list[StreamEvent] = field(default_factory=list)
    final_answer: str = ""
    reasoning_content: str = ""
    usage: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    elapsed_seconds: float = 0.0
