# grok-multiagent-lab

本プロジェクトは、**xAI公式のマルチエージェントモデル**（`grok-4.20-multi-agent-beta-0309`）を対象に、
「本家の挙動をできるだけそのまま観測する」ための Streamlit 検証ラボです。

## 目的

- 本家マルチエージェントの挙動を体験する
- ストリーミング結果を UI 上で逐次表示する
- 取得できる範囲で詳細ログ（verbose streaming）を観測する
- 役割を"自作"せず、**公式モデルの出力のみ**を扱う

## 非目的（やらないこと）

- Researcher / Critic / Synthesizer などの**自前オーケストレーション実装**
- 「内部3体の会話を完全再現した」と見せる疑似表示
- APIで取得できない内部状態の推測表示

## 設計方針

- モデルは原則 `grok-4.20-multi-agent-beta-0309` 固定
- ツールは公式例に合わせて `web_search`, `x_search` を基本利用
- ストリーミングは有効化し、可能なら `include=["verbose_streaming"]` を使用
- UIには「観測できたイベントだけ」を表示する（捏造しない）

## 期待する体験

- 入力欄に自由なお題を入れる
- 実行ボタンでAPIリクエスト開始
- 画面にストリームが流れ、最終回答が組み上がる
- 併設ログ欄にイベント情報・使用量・エラーを時系列表示

## 技術スタック（予定）

- Python 3.13（固定）
- uv（依存管理・仮想環境管理）
- Streamlit
- xAI API（OpenAI互換SDK または xai-sdk）
- 環境変数管理（`.env`）

## 前提条件

1. xAIアカウントを作成済み
2. xAI ConsoleでAPIキー作成済み
3. 利用クレジットが投入済み

参考:
- Quickstart: https://docs.x.ai/developers/quickstart
- Multi Agent: https://docs.x.ai/developers/model-capabilities/text/multi-agent
- Streaming: https://docs.x.ai/developers/model-capabilities/text/streaming
- Release Notes: https://docs.x.ai/developers/release-notes
- Models: https://docs.x.ai/developers/models

## Pythonバージョン固定（uv）

本プロジェクトは **Python 3.13 固定**で運用します。

```bash
uv python pin 3.13
```

これにより `.python-version` が作成され、チーム内でPythonバージョンを揃えやすくなります。

## 環境変数

`.env`（予定）

```bash
XAI_API_KEY=your_api_key_here
```

## 実行イメージ（予定）

```bash
uv python pin 3.13
uv sync
uv run streamlit run app.py
```

## 想定フォルダ構成（案B採用）

```text
grok-multiagent-lab/
  app/
    ui.py                 # Streamlit画面
    client.py             # xAI API呼び出し
    stream_parser.py      # streamingイベント整形
    config.py             # 環境変数/設定
    models.py             # 型定義（任意）
  scripts/
    run_app.sh            # 起動補助（任意）
  logs/
    events/               # 生イベント保存
    sessions/             # 実行セッション単位ログ
  tests/
    test_stream_parser.py
  pyproject.toml
  uv.lock
  .python-version
  .env.example
  README.md
```

## UI仕様（MVP）

- 左ペイン
  - Prompt入力
  - モデル名（初期値固定）
  - ツールON/OFF（web_search, x_search）
  - 実行ボタン

- 右ペイン
  - Streamingテキスト表示（最終回答）
  - Verboseイベントログ（JSON/整形表示）
  - Usage（token情報、処理時間）

## ログ方針

- イベント時刻を必ず記録
- 生イベント（必要なら折りたたみ）を保存
- 失敗時はHTTP status / エラー本文を表示
- 「見えていない内部状態」は明示的に `unknown` 扱い

## 既知の制約

- ベータ機能のため、API仕様が変更される可能性あり
- verbose streaming の項目は将来変更・削除される可能性あり
- "内部エージェント個別ログ"は公開されない場合がある

## 成功条件（MVP）

- Streamlit上で、マルチエージェントモデルの出力がストリーミング表示される
- verbose系イベントを1つ以上UIで確認できる
- 最終回答・使用量・エラー情報を再現可能な形で表示できる

## 次ステップ（README作成後）

1. `pyproject.toml` 作成（uv管理）
2. `app.py` 最小版作成（ストリーミング + ログ）
3. `.env.example` 作成
4. `HOWTO.md` に実行手順とトラブルシュート追記

---

本READMEは「本家観測優先」のため、あえて拡張実装を抑えています。まずは事実として観測できるログを取り、そこから段階的に理解を深めます。
