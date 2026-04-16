"""
毎朝 JST 7:00 に実行され、以下の情報を Slack に通知する。
- ドル円レート
- ユーロ円レート
- 全世界株式（オルカン）・米国株式（S&P500）・バランス（8資産均等型）基準価額
- 都営三田線・JR京浜東北線・小田急線・東急田園都市線・京急線の運行情報
- 米（5kg）平均売価
- ホルムズ海峡通過隻数（直近7日・IMF PortWatch）
"""

import os
import re
import sys
import time
import unicodedata
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

JST = ZoneInfo("Asia/Tokyo")
TIMEOUT = 20
MAX_RETRIES = 2
RETRY_WAIT = 3


def fetch_with_retry(url: str, headers: dict | None = None, params: dict | None = None) -> requests.Response:
    """タイムアウト・リトライ付きの GET リクエストを行う。"""
    for attempt in range(MAX_RETRIES + 1):
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=TIMEOUT)
            resp.raise_for_status()
            return resp
        except Exception:
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_WAIT)
            else:
                raise


def display_width(s: str) -> int:
    """全角文字を幅2、半角を幅1として文字列の表示幅を返す。"""
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in s)


FUNDS = [
    ("0331418A",  "全世界株式（オルカン）"),
    ("03311187",  "米国株式（S&P500）"),
    ("03312175",  "バランス（8資産均等型）"),
]


def get_fx_rates() -> tuple[float, float]:
    """
    frankfurter.app（無料・認証不要）から USD/JPY と EUR/JPY を取得する。
    """
    url = "https://api.frankfurter.app/latest?from=JPY&to=USD,EUR"
    resp = fetch_with_retry(url)
    data = resp.json()
    usd_jpy = round(1 / data["rates"]["USD"], 2)
    eur_jpy = round(1 / data["rates"]["EUR"], 2)
    return usd_jpy, eur_jpy


def get_emaxis_slim_price(fund_code: str) -> int | None:
    """
    minkabu 投資信託 から指定ファンドの基準価額を取得する。
    """
    url = f"https://itf.minkabu.jp/fund/{fund_code}"
    resp = fetch_with_retry(url, headers={"User-Agent": "fetch-market-bot/1.0"})

    soup = BeautifulSoup(resp.text, "html.parser")

    # 構造:
    # <div>
    #   <div>基準価額</div>
    #   <div>
    #     <div>03/09</div>
    #     <div>33,669 円</div>
    #   </div>
    # </div>
    for tag in soup.find_all(string=re.compile(r"^基準価額$")):
        label_el = tag.parent           # <div>基準価額</div>
        price_container = label_el.find_next_sibling()
        if price_container:
            for el in price_container.find_all(True):
                text = el.get_text(strip=True).replace(",", "").replace("円", "").strip()
                if re.fullmatch(r"\d+", text) and int(text) >= 1000:
                    return int(text)

    # フォールバック: ページテキストから「基準価額」直後の価格を抽出
    page_text = soup.get_text("\n", strip=True)
    match = re.search(r"基準価額.*?\n([\d,]+)\s*円", page_text, re.DOTALL)
    if match:
        value = int(match.group(1).replace(",", ""))
        if value >= 1000:
            return value

    return None


TRAIN_LINES = [
    "三田線",
    "京浜東北",
    "小田急",
    "田園都市",
    "京急本線",
]

STATUS_EMOJI = {
    "平常運転": "✅",
    "遅延":     "⚠️",
    "運転見合": "🚫",
    "運転再開": "🔄",
}


def get_train_status() -> list[tuple[str, str, str]]:
    """
    Yahoo!路線情報（首都圏）から対象路線の運行状況を取得する。
    戻り値: [(路線名, ステータス, 詳細), ...]
    """
    url = "https://transit.yahoo.co.jp/traininfo/area/4/"
    resp = fetch_with_retry(url, headers={"User-Agent": "fetch-market-bot/1.0"})

    soup = BeautifulSoup(resp.text, "html.parser")
    results = []

    for tr in soup.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) < 2:
            continue
        route_name = tds[0].get_text(strip=True)
        status     = tds[1].get_text(strip=True)
        detail     = tds[2].get_text(strip=True) if len(tds) > 2 else ""

        if any(line in route_name for line in TRAIN_LINES):
            results.append((route_name, status, detail))

    return results


RICE_API_BASE = "https://price-transition.mdingon.com/Price"
PORTWATCH_CHOKEPOINT_URL = (
    "https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services"
    "/Daily_Chokepoints_Data/FeatureServer/0/query"
)


def get_rice_price() -> tuple[str, int]:
    """
    price-transition.mdingon.com から米（5kg）の平均売価を取得する。
    戻り値: (基準日, currentSimple)
    """
    dates_resp = fetch_with_retry(f"{RICE_API_BASE}/GetAvailableDates")
    latest_date = dates_resp.json()[0]

    price_resp = fetch_with_retry(f"{RICE_API_BASE}/GetPrice?date={latest_date}")
    data = price_resp.json()
    return latest_date, data["currentSimple"]


def get_hormuz_transit() -> list[tuple[str, int]]:
    """
    IMF PortWatch から直近7日分のホルムズ海峡（chokepoint6）通過隻数を取得する。
    戻り値: [(基準日 YYYY-MM-DD, n_total), ...] 日付昇順（古い→新しい）
    """
    params = {
        "where": "portid='chokepoint6'",
        "outFields": "date,year,month,day,n_total",
        "orderByFields": "date DESC",
        "resultRecordCount": 7,
        "f": "json",
    }
    resp = fetch_with_retry(PORTWATCH_CHOKEPOINT_URL, params=params)
    features = resp.json().get("features", [])
    if not features:
        raise ValueError("ホルムズ海峡データが取得できませんでした")
    rows = []
    for feat in reversed(features):  # 古い順に並べ替え
        a = feat["attributes"]
        date_str = f"{a['year']}-{a['month']:02d}-{a['day']:02d}"
        rows.append((date_str, int(a["n_total"])))
    return rows


def send_slack(webhook_url: str, message: str) -> None:
    resp = requests.post(webhook_url, json={"text": message}, timeout=10)
    resp.raise_for_status()


def main() -> None:
    # Windows 環境で絵文字を含む stdout 出力が失敗しないよう UTF-8 に統一
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    dry_run = os.environ.get("DRY_RUN", "").lower() == "true"
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook_url and not dry_run:
        print("Error: 環境変数 SLACK_WEBHOOK_URL が設定されていません。")
        sys.exit(1)

    now = datetime.now(JST)
    date_str = now.strftime("%Y年%m月%d日 %H:%M JST")
    errors: list[str] = []

    # --- 為替レート取得 ---
    try:
        usd_jpy, eur_jpy = get_fx_rates()
        fx_text = f"• ドル円:   *{usd_jpy:,.2f} 円*\n• ユーロ円: *{eur_jpy:,.2f} 円*"
    except Exception as e:
        errors.append(f"為替取得エラー: {e}")
        fx_text = "• 取得に失敗しました"

    # --- 投資信託取得 ---
    max_name_width = max(display_width(name) for _, name in FUNDS)
    fund_lines = []
    for fund_code, fund_name in FUNDS:
        padding = " " * (max_name_width - display_width(fund_name))
        try:
            price = get_emaxis_slim_price(fund_code)
            if price:
                fund_lines.append(f"• {fund_name}{padding}: *{price:,} 円*")
            else:
                fund_lines.append(f"• {fund_name}{padding}: 基準価額を取得できませんでした")
        except Exception as e:
            errors.append(f"投資信託取得エラー ({fund_name}): {e}")
            fund_lines.append(f"• {fund_name}{padding}: 取得に失敗しました")
    fund_text = "\n".join(fund_lines)

    # --- 米価格取得 ---
    try:
        rice_date, rice_price = get_rice_price()
        rice_text = f"• 平均売価: *<https://price-transition.mdingon.com/|{rice_price:,} 円>* （{rice_date} 時点）"
    except Exception as e:
        errors.append(f"米価格取得エラー: {e}")
        rice_text = "• 取得に失敗しました"

    # --- ホルムズ海峡通過隻数取得 ---
    try:
        hormuz_rows = get_hormuz_transit()
        hormuz_lines = [f"• {d}: *{n:,} 隻*" for d, n in hormuz_rows]
        hormuz_text = "\n".join(hormuz_lines)
    except Exception as e:
        errors.append(f"ホルムズ取得エラー: {e}")
        hormuz_text = "• 取得に失敗しました"

    # --- 運行情報取得 ---
    try:
        train_statuses = get_train_status()
        if train_statuses:
            lines = []
            # 小田急3路線をまとめる
            odakyu = [(r, s, d) for r, s, d in train_statuses if "小田急" in r and "多摩線" not in r]
            others = [(r, s, d) for r, s, d in train_statuses if "小田急" not in r]

            for route, status, detail in others:
                emoji = next((v for k, v in STATUS_EMOJI.items() if k in status), "ℹ️")
                line = f"• {emoji} {route}: *{status}*"
                if detail and "ありません" not in detail:
                    line += f"\n   _{detail}_"
                lines.append(line)

            if odakyu:
                # 最も深刻なステータスを代表として表示
                STATUS_PRIORITY = ["運転見合", "遅延", "運転再開", "平常運転"]
                def priority(s):
                    for i, key in enumerate(STATUS_PRIORITY):
                        if key in s:
                            return i
                    return len(STATUS_PRIORITY)

                odakyu_sorted = sorted(odakyu, key=lambda x: priority(x[1]))
                worst_status = odakyu_sorted[0][1]
                emoji = next((v for k, v in STATUS_EMOJI.items() if k in worst_status), "ℹ️")

                if worst_status == "平常運転" or all(s == "平常運転" for _, s, _ in odakyu):
                    lines.append(f"• {emoji} 小田急線（小田原線・江ノ島線）: *平常運転*")
                else:
                    # 異常がある路線のみ詳細表示
                    sub_lines = []
                    for route, status, detail in odakyu:
                        e = next((v for k, v in STATUS_EMOJI.items() if k in status), "ℹ️")
                        sub = f"  - {e} {route}: *{status}*"
                        if detail and "ありません" not in detail:
                            sub += f" _{detail}_"
                        sub_lines.append(sub)
                    lines.append(f"• 小田急線（小田原線・江ノ島線）:\n" + "\n".join(sub_lines))

            train_text = "\n".join(lines)
        else:
            train_text = "• 対象路線の情報が見つかりませんでした"
    except Exception as e:
        errors.append(f"運行情報取得エラー: {e}")
        train_text = "• 取得に失敗しました"

    # --- Slack メッセージ構築 ---
    message = (
        f"📊 *本日の情報* ({date_str})\n"
        f"\n"
        f"🚃 *運行情報*\n{train_text}\n"
        f"\n"
        f"💱 *為替レート*\n{fx_text}\n"
        f"\n"
        f"📈 *投資信託（前営業日基準価額）*\n{fund_text}\n"
        f"\n"
        f"🌾 *米（5kg）税抜価格*\n{rice_text}\n"
        f"\n"
        f"⛴ *ホルムズ海峡 通過隻数*（直近7日・毎週火曜更新・<https://portwatch.imf.org/pages/chokepoint6|IMF PortWatch>）\n{hormuz_text}\n"
        f"\n"
        f"⚡ *エネルギー指標*\n"
        f"🔗 <https://energy-metrics-uydn.vercel.app/|エネルギー価格相関ダッシュボード>"
    )
    if errors:
        message += "\n\n⚠️ *エラー*\n" + "\n".join(f"• {e}" for e in errors)

    if dry_run:
        print("[DRY RUN] Slack 通知はスキップします。")
        print(message)
    else:
        send_slack(webhook_url, message)
        print("Slack 通知を送信しました。")
        print(message)


if __name__ == "__main__":
    main()
