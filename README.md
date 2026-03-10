 ---
  セットアップ手順

  1. Slack Incoming Webhook URL を取得する

  1. https://api.slack.com/apps → "Create New App" → "From scratch"
  2. 左メニュー「Incoming Webhooks」→ 有効化 → "Add New Webhook to Workspace"
  3. 通知したいチャンネルを選択 → URLをコピー

  ---
  2. GitHub にコードをプッシュする

  cd /c/sandbox/study30  
  git init  
  git add .  
  git commit -m "Add daily market info workflow"  
  # GitHub でリポジトリ作成後:  
  git remote add origin https://github.com/あなたのユーザー名/リポジトリ名.git  
  git branch -M main  
  git push -u origin main  

  ---
  3. GitHub Secret に Webhook URL を登録する

  1. GitHubリポジトリ → Settings → Secrets and variables → Actions  
  2. "New repository secret" をクリック  
  3. Name: SLACK_WEBHOOK_URL、Value: コピーしたURL を貼り付けて保存  

  ---
  4. 動作確認（手動実行）

  - GitHubリポジトリ → Actions タブ → Daily Market Info → Run workflow

  ---
  Slack 通知イメージ

  📊 本日の市場情報 (2026年03月10日 07:00 JST)

  💱 為替レート
  • ドル円:   148.52 円
  • ユーロ円: 161.23 円

  📈 投資信託（前営業日基準価額）
  • eMAXIS Slim 全世界株式（オール・カントリー）: 25,432 円

  ---
  注意: eMAXIS Slim は投資信託のため、基準価額は前営業日の値になります（当日リアルタイムは非公開）。また、Yahoo
  ファイナンスのHTML構造が変更された場合は取得ロジックの修正が必要になることがあります。
