# 毎朝の市場情報 Slack 通知

毎朝 JST 7:00 に以下の情報を Slack に自動通知する。

- ドル円・ユーロ円レート
- eMAXIS Slim 全世界株式（オール・カントリー）基準価額
- 都営三田線・JR京浜東北線・小田急線（小田原線・江ノ島線）の運行情報

## 仕組み

```
GitHub Actions（毎朝 UTC 22:00 = JST 7:00）
    ↓
fetch_market.py を実行
    ↓
各情報を取得
    ├─ 為替レート    ← frankfurter.app（無料API）
    ├─ 基準価額      ← minkabu（スクレイピング）
    └─ 運行情報      ← Yahoo!路線情報（スクレイピング）
    ↓
Slack に通知（Incoming Webhook）
```

### GitHub Actions

`.github/workflows/daily_market.yml` で定義されたワークフローが自動実行される。

| 項目 | 内容 |
|------|------|
| 実行タイミング | 毎日 UTC 22:00（JST 翌 7:00）、または手動実行 |
| 実行環境 | GitHub が提供する Ubuntu（無料枠） |
| 処理内容 | Python のセットアップ → ライブラリインストール → スクリプト実行 |
| 認証情報 | Slack Webhook URL は GitHub Secrets で管理（コードに直接書かない） |

### ファイル構成

| ファイル | 役割 |
|----------|------|
| `fetch_market.py` | メインスクリプト。情報取得・Slack通知を行う |
| `requirements.txt` | Python ライブラリの依存定義（requests, beautifulsoup4） |
| `.github/workflows/daily_market.yml` | GitHub Actions のワークフロー定義 |

## Slack 通知イメージ

```
📊 本日の市場情報 (2026年03月10日 07:00 JST)

🚃 運行情報
• ✅ 都営三田線: 平常運転
• ✅ 京浜東北線: 平常運転
• ✅ 小田急線（小田原線・江ノ島線）: 平常運転

💱 為替レート
• ドル円:   148.52 円
• ユーロ円: 161.23 円

📈 投資信託（前営業日基準価額）
• eMAXIS Slim 全世界株式（オール・カントリー）: 25,432 円
```

## 注意

- eMAXIS Slim の基準価額は前営業日の値（当日リアルタイムは非公開）。
- Yahoo!路線情報や minkabu の HTML 構造が変更された場合は取得ロジックの修正が必要になることがある。
