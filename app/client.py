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
    accumulated_reasoning = ""
    last_tool_usage: dict[str, int] = {}

    try:
        for response, chunk in chat.stream():
            ts = now_iso()

            # reasoning_content — 思考テキストの断片
            rc = chunk.reasoning_content if hasattr(chunk, "reasoning_content") else ""
            if rc:
                accumulated_reasoning += rc
                event = StreamEvent(
                    timestamp=ts,
                    event_type="reasoning_delta",
                    data={"reasoning_content": rc},
                )
                result.events.append(event)
                if on_event:
                    on_event(event, result.final_answer)

            # reasoning_tokens カウント（verbose_streaming）
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

            # server_side_tool_usage — ツール使用の変化を検出
            tool_usage: dict[str, int] = {}
            try:
                tool_usage = dict(chunk.server_side_tool_usage) if hasattr(chunk, "server_side_tool_usage") else {}
            except Exception:
                pass
            if tool_usage and tool_usage != last_tool_usage:
                last_tool_usage = tool_usage
                event = StreamEvent(
                    timestamp=ts,
                    event_type="tool_usage",
                    data={"tools": tool_usage},
                )
                result.events.append(event)
                if on_event:
                    on_event(event, result.final_answer)

            # tool_calls — 明示的なツール呼び出し
            try:
                tcs = chunk.tool_calls if hasattr(chunk, "tool_calls") else []
                for tc in tcs:
                    tc_data: dict = {}
                    try:
                        tc_data = {
                            "id": getattr(tc, "id", "unknown"),
                            "name": getattr(tc.function, "name", "unknown") if hasattr(tc, "function") else "unknown",
                            "arguments": getattr(tc.function, "arguments", "") if hasattr(tc, "function") else "",
                        }
                    except Exception:
                        tc_data = {"raw": str(tc)}
                    event = StreamEvent(
                        timestamp=ts,
                        event_type="tool_call",
                        data=tc_data,
                    )
                    result.events.append(event)
                    if on_event:
                        on_event(event, result.final_answer)
            except Exception:
                pass

            # citations — 引用元
            try:
                citations = list(chunk.citations) if hasattr(chunk, "citations") else []
                if citations:
                    event = StreamEvent(
                        timestamp=ts,
                        event_type="citations",
                        data={"urls": citations},
                    )
                    result.events.append(event)
                    if on_event:
                        on_event(event, result.final_answer)
            except Exception:
                pass

            # content — 最終回答テキスト
            if chunk.content:
                if is_thinking:
                    is_thinking = False
                    finish_event = StreamEvent(
                        timestamp=ts,
                        event_type="thinking_done",
                        data={
                            "total_reasoning_tokens": last_reasoning_tokens,
                            "reasoning_text_length": len(accumulated_reasoning),
                        },
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

        # 最終 usage
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

        # reasoning_content 全文を result に保存
        if accumulated_reasoning:
            result.reasoning_content = accumulated_reasoning

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
