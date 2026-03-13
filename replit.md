# Grok Multiagent Lab

xAI公式マルチエージェントモデル（`grok-4.20-multi-agent-beta-0309`）の挙動を観測するための Streamlit 検証ラボ。

## 技術スタック

- **Python**: 3.11
- **フレームワーク**: Streamlit
- **API**: xAI API（OpenAI互換SDK）
- **ポート**: 5000

## フォルダ構成

```
app/
  ui.py             # Streamlit メイン画面
  client.py         # xAI API 呼び出し（ストリーミング）
  stream_parser.py  # ストリーミングイベント整形
  config.py         # 環境変数・設定
  models.py         # 型定義
logs/
  events/           # 生イベント保存（JSON）
  sessions/         # セッション単位ログ（JSON）
tests/
  test_stream_parser.py
.streamlit/
  config.toml       # Streamlit サーバー設定
.env.example        # 環境変数サンプル
pyproject.toml
README.md
```

## 環境変数

| キー | 説明 |
|------|------|
| `XAI_API_KEY` | xAI Console で発行したAPIキー（必須） |

## 起動

```bash
streamlit run app/ui.py
```

## デプロイ

autoscale デプロイ、コマンド:
```
streamlit run app/ui.py --server.port=5000 --server.address=0.0.0.0 --server.headless=true
```

## 設計方針

- モデル固定: `grok-4.20-multi-agent-beta-0309`
- ツール: `web_search`, `x_search`（UI でON/OFF可能）
- ストリーミング有効、`include_usage=True`
- 観測できたイベントのみ表示（捏造なし）
- ログは `logs/sessions/` と `logs/events/` に自動保存
