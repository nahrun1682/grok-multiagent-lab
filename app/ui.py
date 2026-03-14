import sys
import os
import json
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from app.config import DEFAULT_MODEL, AVAILABLE_TOOLS, LOG_DIR_EVENTS, LOG_DIR_SESSIONS
from app.client import stream_completion
from app.models import StreamEvent, SessionResult
from app.stream_parser import format_event_for_display

Path(LOG_DIR_EVENTS).mkdir(parents=True, exist_ok=True)
Path(LOG_DIR_SESSIONS).mkdir(parents=True, exist_ok=True)

st.set_page_config(
    page_title="Grok Multiagent Lab",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
    .main-title {
        font-size: 1.6rem;
        font-weight: 700;
        margin-bottom: 0.2rem;
    }
    .subtitle {
        color: #888;
        font-size: 0.85rem;
        margin-bottom: 1.5rem;
    }
    .event-box {
        background: #1e1e2e;
        border-radius: 6px;
        padding: 10px 14px;
        font-family: monospace;
        font-size: 0.78rem;
        white-space: pre-wrap;
        word-break: break-all;
        margin-bottom: 6px;
        border-left: 3px solid #555;
    }
    .event-content  { border-left-color: #3b82f6; }
    .event-tool     { border-left-color: #f59e0b; }
    .event-usage    { border-left-color: #10b981; }
    .event-finish   { border-left-color: #8b5cf6; }
    .event-error    { border-left-color: #ef4444; }
    .event-thinking { border-left-color: #a78bfa; }
    .event-unknown  { border-left-color: #6b7280; }
    .thinking-card {
        background: #faf5ff;
        border: 1px solid #e9d5ff;
        border-radius: 8px;
        padding: 10px 16px;
        margin-bottom: 10px;
        color: #6d28d9;
        font-size: 0.88rem;
    }
    .usage-card {
        background: #f0fdf4;
        border: 1px solid #bbf7d0;
        border-radius: 8px;
        padding: 12px 16px;
        margin-top: 12px;
    }
    .error-card {
        background: #fef2f2;
        border: 1px solid #fecaca;
        border-radius: 8px;
        padding: 12px 16px;
        margin-top: 12px;
        color: #991b1b;
    }
    .stTextArea textarea { font-size: 0.95rem; }
</style>
""", unsafe_allow_html=True)


def get_event_css_class(event_type: str) -> str:
    if "thinking" in event_type:
        return "event-thinking"
    if "content" in event_type:
        return "event-content"
    if "tool" in event_type:
        return "event-tool"
    if "usage" in event_type:
        return "event-usage"
    if "finish" in event_type:
        return "event-finish"
    if "error" in event_type:
        return "event-error"
    return "event-unknown"


def save_session_log(result: SessionResult, prompt: str) -> str:
    session_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    log_data = {
        "session_id": session_id,
        "prompt": prompt,
        "model": DEFAULT_MODEL,
        "final_answer": result.final_answer,
        "usage": result.usage,
        "error": result.error,
        "elapsed_seconds": result.elapsed_seconds,
        "events": [
            {
                "timestamp": e.timestamp,
                "event_type": e.event_type,
                "data": e.data,
            }
            for e in result.events
        ],
    }
    session_path = Path(LOG_DIR_SESSIONS) / f"{session_id}.json"
    session_path.write_text(json.dumps(log_data, ensure_ascii=False, indent=2))

    events_path = Path(LOG_DIR_EVENTS) / f"{session_id}_raw.json"
    raw_events = [e.raw for e in result.events if e.raw is not None]
    events_path.write_text(json.dumps(raw_events, ensure_ascii=False, indent=2))

    return session_id


st.markdown('<div class="main-title">🔬 Grok Multiagent Lab</div>', unsafe_allow_html=True)
st.markdown(
    f'<div class="subtitle">model: <code>{DEFAULT_MODEL}</code> &nbsp;|&nbsp; xAI公式マルチエージェント観測ラボ</div>',
    unsafe_allow_html=True,
)

left_col, right_col = st.columns([1, 2], gap="large")

with left_col:
    st.subheader("設定 / 入力")

    prompt = st.text_area(
        "プロンプト",
        placeholder="お題を入力してください（例: 最新のAIニュースを教えて）",
        height=180,
        key="prompt_input",
    )

    st.caption(f"モデル: `{DEFAULT_MODEL}`（固定）")

    st.markdown("**ツール**")
    enabled_tools: list[str] = []
    for tool_name in AVAILABLE_TOOLS:
        if st.checkbox(tool_name, value=True, key=f"tool_{tool_name}"):
            enabled_tools.append(tool_name)

    st.divider()
    run_button = st.button("▶ 実行", type="primary", use_container_width=True)

    if "last_session_id" in st.session_state and st.session_state.last_session_id:
        st.caption(f"最終セッション: `{st.session_state.last_session_id}`")


if "result" not in st.session_state:
    st.session_state.result = None
if "running" not in st.session_state:
    st.session_state.running = False
if "last_session_id" not in st.session_state:
    st.session_state.last_session_id = ""

with right_col:
    answer_header = st.empty()
    answer_container = st.empty()
    divider_placeholder = st.empty()
    log_header = st.empty()
    log_container = st.empty()
    usage_container = st.empty()

    answer_header.subheader("最終回答")

    if not run_button:
        if st.session_state.result is None:
            answer_container.info("左ペインでプロンプトを入力して「実行」を押してください。")
        else:
            result: SessionResult = st.session_state.result
            if result.final_answer:
                answer_container.markdown(result.final_answer)
            if result.error:
                answer_container.markdown(
                    f'<div class="error-card">❌ エラー: {result.error}</div>',
                    unsafe_allow_html=True,
                )

            divider_placeholder.divider()
            log_header.subheader("イベントログ")

            with log_container.container():
                for event in result.events:
                    css_class = get_event_css_class(event.event_type)
                    label = format_event_for_display(event)
                    with st.expander(f"`{event.event_type}` — {event.timestamp}", expanded=False):
                        st.text(label)
                        if event.raw:
                            st.json(event.raw)

            if result.usage:
                with usage_container.container():
                    st.markdown(
                        f'<div class="usage-card">'
                        f'⚡ <strong>Usage</strong> &nbsp;'
                        f'prompt: <strong>{result.usage.get("prompt_tokens", "?")}tok</strong> &nbsp;'
                        f'completion: <strong>{result.usage.get("completion_tokens", "?")}tok</strong> &nbsp;'
                        f'total: <strong>{result.usage.get("total_tokens", "?")}tok</strong> &nbsp;'
                        f'elapsed: <strong>{result.elapsed_seconds:.2f}s</strong>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

if run_button:
    if not prompt.strip():
        with right_col:
            answer_container.warning("プロンプトを入力してください。")
    else:
        answer_header.subheader("最終回答")
        answer_placeholder = answer_container.empty()
        divider_placeholder.divider()
        log_header.subheader("イベントログ")

        accumulated_answer = ""
        collected_events: list[StreamEvent] = []

        answer_placeholder.markdown(
            '<div class="thinking-card">🤔 マルチエージェント起動中...</div>',
            unsafe_allow_html=True,
        )

        def on_event(event: StreamEvent, current_answer: str) -> None:
            collected_events.append(event)

            if event.event_type == "thinking":
                rtok = event.data.get("reasoning_tokens", 0)
                answer_placeholder.markdown(
                    f'<div class="thinking-card">🧠 Thinking... ({rtok} reasoning tokens)</div>',
                    unsafe_allow_html=True,
                )
            elif event.event_type == "thinking_done":
                rtok = event.data.get("total_reasoning_tokens", 0)
                answer_placeholder.markdown(
                    f'<div class="thinking-card">✅ Thinking 完了 ({rtok} reasoning tokens) — 回答生成中...</div>',
                    unsafe_allow_html=True,
                )
            elif event.event_type == "content_delta":
                answer_placeholder.markdown(current_answer + "▌")

        result = stream_completion(
            prompt=prompt.strip(),
            enabled_tools=enabled_tools,
            on_event=on_event,
        )

        if result.final_answer:
            answer_placeholder.markdown(result.final_answer)
        elif result.error:
            answer_placeholder.markdown(
                f'<div class="error-card">❌ エラー: {result.error}</div>',
                unsafe_allow_html=True,
            )
        else:
            answer_placeholder.markdown("_(回答なし)_")

        with log_container.container():
            for event in result.events:
                css_class = get_event_css_class(event.event_type)
                label = format_event_for_display(event)
                with st.expander(f"`{event.event_type}` — {event.timestamp}", expanded=(event.event_type == "error")):
                    st.text(label)
                    if event.raw:
                        st.json(event.raw)

        if result.usage:
            with usage_container.container():
                st.markdown(
                    f'<div class="usage-card">'
                    f'⚡ <strong>Usage</strong> &nbsp;'
                    f'prompt: <strong>{result.usage.get("prompt_tokens", "?")}tok</strong> &nbsp;'
                    f'completion: <strong>{result.usage.get("completion_tokens", "?")}tok</strong> &nbsp;'
                    f'total: <strong>{result.usage.get("total_tokens", "?")}tok</strong> &nbsp;'
                    f'elapsed: <strong>{result.elapsed_seconds:.2f}s</strong>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        session_id = save_session_log(result, prompt.strip())
        st.session_state.result = result
        st.session_state.last_session_id = session_id
