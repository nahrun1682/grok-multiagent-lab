import sys
import os
import json
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
    .main-title { font-size: 1.5rem; font-weight: 700; margin-bottom: 0.1rem; }
    .subtitle { color: #888; font-size: 0.82rem; margin-bottom: 1rem; }
    .thinking-card {
        background: #faf5ff; border: 1px solid #e9d5ff;
        border-radius: 8px; padding: 8px 14px;
        color: #6d28d9; font-size: 0.85rem; margin-bottom: 8px;
    }
    .tool-badge {
        display: inline-block; background: #fef3c7;
        border: 1px solid #fcd34d; color: #92400e;
        padding: 2px 10px; border-radius: 9999px;
        font-size: 0.78rem; margin: 2px;
    }
    .usage-card {
        background: #f0fdf4; border: 1px solid #bbf7d0;
        border-radius: 8px; padding: 10px 14px; margin-top: 8px; font-size: 0.85rem;
    }
    .error-card {
        background: #fef2f2; border: 1px solid #fecaca;
        border-radius: 8px; padding: 10px 14px; color: #991b1b; font-size: 0.85rem;
    }
    .reasoning-box {
        background: #1e1b2e; color: #c4b5fd;
        font-family: monospace; font-size: 0.78rem;
        padding: 12px; border-radius: 6px;
        white-space: pre-wrap; word-break: break-all;
        max-height: 400px; overflow-y: auto;
    }
    .citation-item { font-size: 0.8rem; color: #2563eb; word-break: break-all; }
    .stTextArea textarea { font-size: 0.92rem; }
</style>
""", unsafe_allow_html=True)


def get_event_icon(event_type: str) -> str:
    icons = {
        "reasoning_delta": "🧠",
        "thinking": "⏳",
        "thinking_done": "✅",
        "tool_usage": "🔧",
        "tool_call": "🛠️",
        "citations": "🔗",
        "content_delta": "📝",
        "usage": "⚡",
        "error": "❌",
    }
    for k, v in icons.items():
        if k in event_type:
            return v
    return "◽"


def save_session_log(result: SessionResult, prompt: str) -> str:
    session_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    log_data = {
        "session_id": session_id,
        "prompt": prompt,
        "model": DEFAULT_MODEL,
        "final_answer": result.final_answer,
        "reasoning_content": result.reasoning_content,
        "usage": result.usage,
        "error": result.error,
        "elapsed_seconds": result.elapsed_seconds,
        "events": [
            {"timestamp": e.timestamp, "event_type": e.event_type, "data": e.data}
            for e in result.events
        ],
    }
    (Path(LOG_DIR_SESSIONS) / f"{session_id}.json").write_text(
        json.dumps(log_data, ensure_ascii=False, indent=2)
    )
    return session_id


def render_result_tabs(result: SessionResult) -> None:
    tab_answer, tab_reasoning, tab_events = st.tabs(["📄 最終回答", "🧠 思考ログ", "📋 イベントログ"])

    with tab_answer:
        if result.error:
            st.markdown(
                f'<div class="error-card">❌ {result.error}</div>',
                unsafe_allow_html=True,
            )
        elif result.final_answer:
            st.markdown(result.final_answer)
        else:
            st.info("_(回答なし)_")

        # ツール使用サマリ
        tool_events = [e for e in result.events if e.event_type == "tool_usage"]
        if tool_events:
            last = tool_events[-1]
            tools_html = "".join(
                f'<span class="tool-badge">{name} × {count}</span>'
                for name, count in last.data.get("tools", {}).items()
            )
            st.markdown(f"**使用ツール:** {tools_html}", unsafe_allow_html=True)

        # 引用
        cite_events = [e for e in result.events if e.event_type == "citations"]
        if cite_events:
            all_urls: list[str] = []
            for e in cite_events:
                all_urls.extend(e.data.get("urls", []))
            if all_urls:
                with st.expander(f"🔗 引用元 ({len(all_urls)}件)", expanded=False):
                    for url in all_urls:
                        st.markdown(f'<div class="citation-item">{url}</div>', unsafe_allow_html=True)

        # Usage
        if result.usage:
            st.markdown(
                f'<div class="usage-card">'
                f'⚡ prompt: <strong>{result.usage.get("prompt_tokens", "?")}tok</strong> &nbsp;'
                f'completion: <strong>{result.usage.get("completion_tokens", "?")}tok</strong> &nbsp;'
                f'reasoning: <strong>{result.usage.get("reasoning_tokens", "?")}tok</strong> &nbsp;'
                f'total: <strong>{result.usage.get("total_tokens", "?")}tok</strong> &nbsp;'
                f'elapsed: <strong>{result.elapsed_seconds:.1f}s</strong>'
                f'</div>',
                unsafe_allow_html=True,
            )

    with tab_reasoning:
        st.caption("verbose_streaming で観測できた reasoning_content（思考テキスト）を表示します。取得できなかった場合は空欄です。")
        if result.reasoning_content:
            st.markdown(
                f'<div class="reasoning-box">{result.reasoning_content}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.info(
                "reasoning_content は観測されませんでした。\n\n"
                "**xAI公式仕様による制約：**\n"
                "- サブエージェント個別の会話・ツール呼び出しは暗号化されており、APIからは取得不可\n"
                "- `verbose_streaming` では reasoning_tokens（思考トークン数）のみが公開されている\n"
                "- 内部エージェント間のやりとりは `unknown` 扱い（README の設計方針通り）"
            )

    with tab_events:
        st.caption(f"全 {len(result.events)} イベント")
        SKIP_IN_LOG = {"content_delta", "reasoning_delta"}
        display_events = [e for e in result.events if e.event_type not in SKIP_IN_LOG]

        for event in display_events:
            icon = get_event_icon(event.event_type)
            expanded = event.event_type in ("error", "tool_call", "tool_usage", "citations", "usage", "thinking_done")
            with st.expander(
                f"{icon} `{event.event_type}` — {event.timestamp}",
                expanded=expanded,
            ):
                st.text(format_event_for_display(event))
                if event.data:
                    st.json(event.data)

        # content_delta は件数だけ表示
        content_events = [e for e in result.events if e.event_type == "content_delta"]
        reasoning_events = [e for e in result.events if e.event_type == "reasoning_delta"]
        if content_events or reasoning_events:
            st.caption(
                f"※ content_delta: {len(content_events)}件、reasoning_delta: {len(reasoning_events)}件 は省略（「最終回答」「思考ログ」タブを参照）"
            )


# ────────────────────────────
# メインレイアウト
# ────────────────────────────
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
if "last_session_id" not in st.session_state:
    st.session_state.last_session_id = ""

with right_col:
    if not run_button:
        if st.session_state.result is None:
            st.info("左ペインでプロンプトを入力して「実行」を押してください。")
        else:
            render_result_tabs(st.session_state.result)

if run_button:
    if not prompt.strip():
        with right_col:
            st.warning("プロンプトを入力してください。")
    else:
        with right_col:
            # ライブ表示用プレースホルダ
            status_ph = st.empty()
            answer_ph = st.empty()
            tool_ph = st.empty()

            status_ph.markdown(
                '<div class="thinking-card">🤔 マルチエージェント起動中...</div>',
                unsafe_allow_html=True,
            )

            live_tools: dict[str, int] = {}

            def on_event(event: StreamEvent, current_answer: str) -> None:
                if event.event_type == "thinking":
                    rtok = event.data.get("reasoning_tokens", 0)
                    status_ph.markdown(
                        f'<div class="thinking-card">🧠 Thinking... ({rtok:,} reasoning tokens)</div>',
                        unsafe_allow_html=True,
                    )
                elif event.event_type == "reasoning_delta":
                    pass  # 蓄積はclient側で実施、ここでは更新しない（重い）
                elif event.event_type == "tool_usage":
                    live_tools.update(event.data.get("tools", {}))
                    badges = "".join(
                        f'<span class="tool-badge">{n} × {c}</span>'
                        for n, c in live_tools.items()
                    )
                    tool_ph.markdown(f"🔧 **ツール使用中:** {badges}", unsafe_allow_html=True)
                elif event.event_type == "thinking_done":
                    rtok = event.data.get("total_reasoning_tokens", 0)
                    status_ph.markdown(
                        f'<div class="thinking-card">✅ 思考完了 ({rtok:,} tokens) — 回答生成中...</div>',
                        unsafe_allow_html=True,
                    )
                elif event.event_type == "content_delta":
                    status_ph.empty()
                    answer_ph.markdown(current_answer + "▌")

            result = stream_completion(
                prompt=prompt.strip(),
                enabled_tools=enabled_tools,
                on_event=on_event,
            )

            status_ph.empty()
            tool_ph.empty()
            answer_ph.empty()

            session_id = save_session_log(result, prompt.strip())
            st.session_state.result = result
            st.session_state.last_session_id = session_id

            render_result_tabs(result)
