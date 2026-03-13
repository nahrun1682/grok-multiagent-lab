import time
from typing import Callable, Any
from openai import OpenAI
from app.config import XAI_API_KEY, BASE_URL, DEFAULT_MODEL
from app.stream_parser import parse_chunk, now_iso
from app.models import SessionResult, StreamEvent


TOOL_DEFINITIONS: dict[str, dict] = {
    "web_search": {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the web for current information",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"}
                },
                "required": ["query"],
            },
        },
    },
    "x_search": {
        "type": "function",
        "function": {
            "name": "x_search",
            "description": "Search X (formerly Twitter) for posts and information",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"}
                },
                "required": ["query"],
            },
        },
    },
}


def stream_completion(
    prompt: str,
    enabled_tools: list[str],
    on_event: Callable[[StreamEvent, str], None] | None = None,
) -> SessionResult:
    if not XAI_API_KEY:
        result = SessionResult()
        result.error = "XAI_API_KEY が設定されていません。環境変数を確認してください。"
        result.events.append(StreamEvent(
            timestamp=now_iso(),
            event_type="error",
            data={"error": result.error},
        ))
        return result

    client = OpenAI(api_key=XAI_API_KEY, base_url=BASE_URL)
    result = SessionResult()

    tools: list[dict] = [
        TOOL_DEFINITIONS[t] for t in enabled_tools if t in TOOL_DEFINITIONS
    ]

    kwargs: dict[str, Any] = {
        "model": DEFAULT_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": True,
        "stream_options": {"include_usage": True},
    }
    if tools:
        kwargs["tools"] = tools

    start = time.time()

    try:
        stream = client.chat.completions.create(**kwargs)
        for chunk in stream:
            event = parse_chunk(chunk)
            result.events.append(event)

            if event.event_type == "content_delta":
                result.final_answer += event.data.get("content", "")
            elif event.event_type == "usage":
                result.usage = event.data

            if on_event:
                on_event(event, result.final_answer)

    except Exception as e:
        error_msg = str(e)
        result.error = error_msg
        result.events.append(StreamEvent(
            timestamp=now_iso(),
            event_type="error",
            data={"error": error_msg},
        ))
        if on_event:
            on_event(result.events[-1], result.final_answer)

    result.elapsed_seconds = time.time() - start
    return result
