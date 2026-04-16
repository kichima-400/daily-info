# 毎朝の市場情報 Slack 通知

**リポジトリ:** https://github.com/kichima-400/daily-info

2種類の自動通知を行う。

**JST 7:00** — 市場・運行情報
- ドル円・ユーロ円レート
- 全世界株式（オルカン）・米国株式（S&P500）・バランス（8資産均等型）基準価額
- 米（5kg）平均売価（税抜き）
- ホルムズ海峡通過隻数（直近7日・IMF PortWatch）
- 都営三田線・JR京浜東北線・小田急線・東急田園都市線・京急本線の運行情報

**JST 11:30** — 新商品人気ランキング
- mdingon.com の RDS ランキング（毎朝 10:00 JST 更新）をスクレイピング

## 仕組み

```
GitHub Actions（毎朝 UTC 22:00 = JST 7:00）
    ↓
fetch_market.py を実行
    ↓
各情報を取得
    ├─ 為替レート    ← frankfurter.app（無料API）
    ├─ 基準価額      ← minkabu（スクレイピング）
    ├─ 米価格        ← price-transition.mdingon.com（無料API）
    ├─ 通過隻数      ← IMF PortWatch ArcGIS REST API（無料・週次更新）
    └─ 運行情報      ← Yahoo!路線情報（スクレイピング）
    ↓
Slack に通知（Incoming Webhook）

GitHub Actions（毎日 UTC 02:30 = JST 11:30）
    ↓
fetch_new_products.py を実行
    ↓
新商品ランキングを取得
    └─ RDS ランキング ← mdingon.com（スクレイピング）
    ↓
Slack に通知（Incoming Webhook）
```

### GitHub Actions

| ワークフロー | 実行タイミング | 内容 |
|---|---|---|
| `daily_market.yml` | 毎日 UTC 22:00（JST 7:00） | 市場・運行情報通知（本番） |
| `dev_market.yml` | 手動のみ | 市場・運行情報通知（DRY RUN） |
| `new_products.yml` | 毎日 UTC 02:30（JST 11:30） | 新商品ランキング通知（本番） |
| `dev_new_products.yml` | 手動のみ | 新商品ランキング通知（DRY RUN） |

### ファイル構成

| ファイル | 役割 |
|----------|------|
| `fetch_market.py` | 市場・運行情報取得・Slack通知 |
| `fetch_new_products.py` | 新商品ランキング取得・Slack通知 |
| `requirements.txt` | Python ライブラリの依存定義（requests, beautifulsoup4） |
| `.github/workflows/daily_market.yml` | 本番ワークフロー（毎日自動実行） |
| `.github/workflows/dev_market.yml` | 開発用ワークフロー（手動・DRY RUN） |
| `.github/workflows/new_products.yml` | 新商品ランキング本番ワークフロー |
| `.github/workflows/dev_new_products.yml` | 新商品ランキング開発用ワークフロー（手動・DRY RUN） |

## Slack 通知イメージ

### JST 7:00 — 市場・運行情報

```
📊 本日の情報 (2026年03月10日 07:00 JST)

🚃 運行情報
• ✅ 京浜東北根岸線: 平常運転
• ✅ 東急田園都市線: 平常運転
• ✅ 都営三田線: 平常運転
• ✅ 京急本線: 平常運転
• ✅ 小田急線（小田原線・江ノ島線）: 平常運転

💱 為替レート
• ドル円:   148.52 円
• ユーロ円: 161.23 円

📈 投資信託（前営業日基準価額）
• 全世界株式（オルカン） : 25,432 円
• 米国株式（S&P500）     : 30,123 円
• バランス（8資産均等型）: 18,765 円

🌾 米（5kg）税抜価格
• 平均売価: 3,848 円 （2026-03-17 時点）

⛴ ホルムズ海峡 通過隻数（直近7日・毎週火曜更新・IMF PortWatch）
• 2026-03-11: 38 隻
• 2026-03-12: 42 隻
• ...
• 2026-03-17: 44 隻

⚡ エネルギー指標
🔗 エネルギー価格相関ダッシュボード
```

### JST 11:30 — 新商品人気ランキング

```
🆕 新商品人気ランキング (2026年03月18日 11:30 JST)
RDSランキング（2026-03-16 時点）

1位 🆕 フルタ チョコエッグ ポケットモンスター旅立ちの３匹 20g
   フルタ製菓 | JAN: 4902501210239
2位 📉 ハーゲンダッツ ミニカップ ROCKYCRUNCHY! ソルティハニーバター 87ml
   ハーゲンダッツジャパン | JAN: 4976994207151
3位 📉 ハーゲンダッツ ミニカップ ROCKYCRUNCHY! ストロベリーブラックココア 88ml
   ハーゲンダッツジャパン | JAN: 4976994207168
```

## 注意

- eMAXIS Slim の基準価額は前営業日の値（当日リアルタイムは非公開）。
- 米価格は税抜き表示（軽減税率8%対象）。データは RDS-POS 提供で1日3回更新。
- ホルムズ海峡通過隻数は IMF PortWatch（IMF / Oxford 提供）による週次更新データ（毎週火曜 JST 23:00）のため、最大7日程度のラグがある。GPS ジャミング・AIS スプーフィングの影響を受ける可能性あり。
- 新商品ランキングは mdingon.com の HTML 構造に依存しており、変更時は修正が必要。
- Yahoo!路線情報や minkabu の HTML 構造が変更された場合は取得ロジックの修正が必要になることがある。
