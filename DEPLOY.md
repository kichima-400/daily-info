# デプロイ手順

## 1. Slack Incoming Webhook URL を取得する

1. https://api.slack.com/apps → "Create New App" → "From scratch"
2. 左メニュー「Incoming Webhooks」→ 有効化 → "Add New Webhook to Workspace"
3. 通知したいチャンネルを選択 → URL をコピー

## 2. GitHub Secret に Webhook URL を登録する

1. GitHub リポジトリ → Settings → Secrets and variables → Actions
2. "New repository secret" をクリック
3. Name: `SLACK_WEBHOOK_URL`、Value: コピーした URL を貼り付けて保存

> **注意:** 登録済みかどうかは上記画面で確認できるが、セキュリティ上の仕様により登録した URL の値は表示されない。値を確認したい場合は一度削除して再登録する。

## 3. 動作確認

### Slack 通知なしで確認する（開発用）

GitHub リポジトリ → Actions タブ → **Dev Market Info (Dry Run)** → "Run workflow"

`SLACK_WEBHOOK_URL` の設定不要。実行ログにメッセージ内容が出力される。

### Slack に実際に通知して確認する

GitHub リポジトリ → Actions タブ → **Daily Market Info** → "Run workflow"
