import time
from typing import Callable
from xai_sdk import Client
from xai_sdk.chat import user as xai_user
from xai_sdk.tools import web_search as xai_web_search, x_search as xai_x_search
from app.config import XAI_API_KEY, DEFAULT_MODEL
from app.stream_parser import now_iso
from app.models import SessionResult, StreamEvent


AVAILABLE_TOOL_FACTORIES = {
    "web_search": xai_web_search,
    "x_search": xai_x_search,
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

    client = Client(api_key=XAI_API_KEY)
    result = SessionResult()

    tools = [
        AVAILABLE_TOOL_FACTORIES[t]()
        for t in enabled_tools
        if t in AVAILABLE_TOOL_FACTORIES
    ]

    chat_kwargs = dict(
        model=DEFAULT_MODEL,
        include=["verbose_streaming"],
    )
    if tools:
        chat_kwargs["tools"] = tools

    chat = client.chat.create(**chat_kwargs)
    chat.append(xai_user(prompt))

    start = time.time()
    is_thinking = True
    last_reasoning_tokens = 0

    try:
        for response, chunk in chat.stream():
            ts = now_iso()

            reasoning_tokens = getattr(response.usage, "reasoning_tokens", 0) or 0

            if reasoning_tokens and reasoning_tokens != last_reasoning_tokens and is_thinking:
                last_reasoning_tokens = reasoning_tokens
                event = StreamEvent(
                    timestamp=ts,
                    event_type="thinking",
                    data={"reasoning_tokens": reasoning_tokens},
                )
                result.events.append(event)
                if on_event:
                    on_event(event, result.final_answer)

            if chunk.content:
                if is_thinking:
                    is_thinking = False
                    finish_event = StreamEvent(
                        timestamp=ts,
                        event_type="thinking_done",
                        data={"total_reasoning_tokens": last_reasoning_tokens},
                    )
                    result.events.append(finish_event)
                    if on_event:
                        on_event(finish_event, result.final_answer)

                result.final_answer += chunk.content
                event = StreamEvent(
                    timestamp=ts,
                    event_type="content_delta",
                    data={"content": chunk.content},
                )
                result.events.append(event)
                if on_event:
                    on_event(event, result.final_answer)

        if response and response.usage:
            usage_data = {
                "prompt_tokens": getattr(response.usage, "prompt_tokens", "unknown"),
                "completion_tokens": getattr(response.usage, "completion_tokens", "unknown"),
                "reasoning_tokens": getattr(response.usage, "reasoning_tokens", "unknown"),
                "total_tokens": getattr(response.usage, "total_tokens", "unknown"),
            }
            result.usage = usage_data
            usage_event = StreamEvent(
                timestamp=now_iso(),
                event_type="usage",
                data=usage_data,
            )
            result.events.append(usage_event)
            if on_event:
                on_event(usage_event, result.final_answer)

    except Exception as e:
        error_msg = str(e)
        result.error = error_msg
        err_event = StreamEvent(
            timestamp=now_iso(),
            event_type="error",
            data={"error": error_msg},
        )
        result.events.append(err_event)
        if on_event:
            on_event(err_event, result.final_answer)

    result.elapsed_seconds = time.time() - start
    return result
