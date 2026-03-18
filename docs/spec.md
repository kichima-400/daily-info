# 仕様書: fetch_market.py

## 概要

毎朝 JST 7:00 に GitHub Actions で実行され、為替レート・投資信託基準価額・米価格・電車運行情報を取得して Slack に通知する Python スクリプト。

---

## ファイル構成

```
fetch_market.py                        # メインスクリプト
requirements.txt                       # 依存ライブラリ
.github/workflows/daily_market.yml    # 本番ワークフロー（毎日自動実行）
.github/workflows/dev_market.yml      # 開発ワークフロー（手動実行・DRY RUN）
```

---

## 依存ライブラリ

| ライブラリ | バージョン | 用途 |
|---|---|---|
| requests | 2.32.3 | HTTP リクエスト |
| beautifulsoup4 | 4.12.3 | HTML スクレイピング |

標準ライブラリ: `os`, `re`, `sys`, `time`, `unicodedata`, `datetime`, `zoneinfo`

---

## 定数

| 定数 | 値 | 説明 |
|---|---|---|
| `JST` | `ZoneInfo("Asia/Tokyo")` | 日本標準時 |
| `TIMEOUT` | `20` | HTTP リクエストタイムアウト（秒） |
| `MAX_RETRIES` | `2` | リトライ最大回数 |
| `RETRY_WAIT` | `3` | リトライ間隔（秒） |
| `RICE_API_BASE` | `https://price-transition.mdingon.com/Price` | 米価格 API のベース URL |

---

## 関数仕様

### `fetch_with_retry(url, headers=None) -> requests.Response`

タイムアウト・リトライ付きの GET リクエストを行う。

- `MAX_RETRIES` 回まで失敗時に `RETRY_WAIT` 秒待ってリトライ
- 全リトライ失敗時は例外をそのまま raise

---

### `display_width(s) -> int`

全角文字を幅 2、半角を幅 1 として文字列の表示幅を返す。

- `unicodedata.east_asian_width` が `"W"` または `"F"` の場合を全角とみなす
- ファンド名のパディング計算に使用

---

### `get_fx_rates() -> tuple[float, float]`

frankfurter.app から USD/JPY と EUR/JPY を取得する。

- **エンドポイント**: `https://api.frankfurter.app/latest?from=JPY&to=USD,EUR`
- **認証**: 不要
- **戻り値**: `(usd_jpy, eur_jpy)` — 小数点2桁に丸めた float

---

### `get_emaxis_slim_price(fund_code) -> int | None`

minkabu 投資信託ページから指定ファンドの基準価額を取得する。

- **URL**: `https://itf.minkabu.jp/fund/{fund_code}`
- **User-Agent**: `fetch-market-bot/1.0`
- **戻り値**: 基準価額（整数・円）、取得失敗時は `None`

**スクレイピング手順（優先順）:**

1. `"基準価額"` テキストを持つ要素を探し、その兄弟要素から `\d+` かつ `>= 1000` の数値を取得
2. フォールバック: ページ全体テキストから `基準価額.*?\n([\d,]+)\s*円` の正規表現で抽出

**対象ファンド:**

| ファンドコード | ファンド名 |
|---|---|
| `0331418A` | 全世界株式（オルカン） |
| `03311187` | 米国株式（S&P500） |
| `03312175` | バランス（8資産均等型） |

---

### `get_train_status() -> list[tuple[str, str, str]]`

Yahoo!路線情報（首都圏）から対象路線の運行状況を取得する。

- **URL**: `https://transit.yahoo.co.jp/traininfo/area/4/`
- **User-Agent**: `fetch-market-bot/1.0`
- **戻り値**: `[(路線名, ステータス, 詳細), ...]`
- `<tr>` 要素内の `<td>` をパース（td[0]=路線名, td[1]=ステータス, td[2]=詳細）

**対象路線（部分一致）:**

| キーワード | 対象路線 |
|---|---|
| `三田線` | 都営三田線 |
| `京浜東北` | JR 京浜東北線 |
| `小田急` | 小田急小田原線・江ノ島線（多摩線は除外） |
| `田園都市` | 東急田園都市線 |
| `京急本線` | 京急本線 |

**小田急線の統合処理:**

- 多摩線を除く小田急 3 路線（小田原線・江ノ島線等）は 1 エントリにまとめる
- 全路線が平常運転の場合: `小田急線（小田原線・江ノ島線）: 平常運転` と表示
- 異常がある場合: 路線ごとに詳細を展開表示
- 複数路線に異常がある場合は最も深刻なステータスを代表表示（優先順: 運転見合 > 遅延 > 運転再開 > 平常運転）

**ステータス絵文字マッピング:**

| ステータス（部分一致） | 絵文字 |
|---|---|
| 平常運転 | ✅ |
| 遅延 | ⚠️ |
| 運転見合 | 🚫 |
| 運転再開 | 🔄 |
| その他 | ℹ️ |

---

### `get_rice_price() -> tuple[str, int]`

price-transition.mdingon.com から米（5kg）の平均売価を取得する。

- **エンドポイント1**: `GET /Price/GetAvailableDates` — 利用可能な日付一覧を取得し、先頭（最新日）を使用
- **エンドポイント2**: `GET /Price/GetPrice?date=YYYY-MM-DD` — 指定日の価格データを取得
- **認証**: 不要
- **戻り値**: `(基準日, currentSimple)` — currentSimple は全商品の総売上÷総数量による平均売価（税抜き）
- **データソース**: RDS-POS（株式会社マーチャンダイジング・オン）、1日3回更新
- **税区分**: 税抜き（食品の軽減税率8%対象。税込換算は×1.08）

---

### `send_slack(webhook_url, message) -> None`

Slack Incoming Webhook に POST する。タイムアウト 10 秒。

---

### `main() -> None`

エントリポイント。以下の順で処理する。

1. 環境変数チェック（`SLACK_WEBHOOK_URL` 未設定かつ非 DRY RUN の場合は exit 1）
2. 為替レート取得
3. 投資信託基準価額取得（3 ファンド）
4. 米価格取得
5. 電車運行情報取得
6. Slack メッセージ構築・送信（または DRY RUN 時は stdout 出力）

各取得処理は独立した try/except で囲まれており、1 つの失敗が他に影響しない。

---

## Slack メッセージフォーマット

```
📊 *本日の情報* (YYYY年MM月DD日 HH:MM JST)

🚃 *運行情報*
• ✅ 三田線: *平常運転*
• ✅ 京浜東北線: *平常運転*
...

💱 *為替レート*
• ドル円:   *149.50 円*
• ユーロ円: *162.30 円*

📈 *投資信託（前営業日基準価額）*
• 全世界株式（オルカン）      : *25,000 円*
• 米国株式（S&P500）          : *30,000 円*
• バランス（8資産均等型）     : *15,000 円*

🌾 *米（5kg）価格*
• 平均売価: *3,848 円* （税抜・2026-03-17 時点）

⚡ *エネルギー指標*
🔗 <https://energy-metrics-uydn.vercel.app/|エネルギー価格相関ダッシュボード>

⚠️ *エラー*   ← 取得失敗があった場合のみ表示
• 為替取得エラー: ...
```

---

## 環境変数

| 変数名 | 必須 | 説明 |
|---|---|---|
| `SLACK_WEBHOOK_URL` | 本番時必須 | Slack Incoming Webhook URL |
| `DRY_RUN` | 任意 | `"true"` に設定すると Slack 送信をスキップして stdout に出力 |

---

## GitHub Actions ワークフロー

### daily_market.yml（本番）

| 項目 | 値 |
|---|---|
| トリガー | スケジュール（UTC 22:00 = JST 07:00）、手動実行 |
| 実行環境 | ubuntu-latest |
| Python バージョン | 3.11 |
| Secrets | `SLACK_WEBHOOK_URL` |

### dev_market.yml（開発）

| 項目 | 値 |
|---|---|
| トリガー | 手動実行のみ（workflow_dispatch） |
| 実行環境 | ubuntu-latest |
| Python バージョン | 3.11 |
| 環境変数 | `DRY_RUN=true`（Slack 送信スキップ） |

---

## 制約・注意事項

- ファンド基準価額は**前営業日**の値（リアルタイムではない）
- 米価格は**税抜き**（軽減税率8%対象）。税込換算は×1.08
- 米価格データは RDS-POS（株式会社マーチャンダイジング・オン）提供、1日3回更新
- minkabu.jp・Yahoo!路線情報の HTML 構造が変わるとスクレイピングが壊れる
- User-Agent はブラウザスプーフではなく正直なボット識別子（`fetch-market-bot/1.0`）を使用
- 小田急多摩線はモニタリング対象外
