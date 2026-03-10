"""
毎朝 JST 7:00 に実行され、以下の情報を Slack に通知する。
- ドル円レート
- ユーロ円レート
- eMAXIS Slim 全世界株式（オール・カントリー）基準価額
- 都営三田線・JR京浜東北線・小田急線の運行情報
"""

import os
import re
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

JST = ZoneInfo("Asia/Tokyo")
EMAXIS_SLIM_CODE = "0331418A"  # eMAXIS Slim 全世界株式（オール・カントリー）


def get_fx_rates() -> tuple[float, float]:
    """
    frankfurter.app（無料・認証不要）から USD/JPY と EUR/JPY を取得する。
    """
    url = "https://api.frankfurter.app/latest?from=JPY&to=USD,EUR"
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    usd_jpy = round(1 / data["rates"]["USD"], 2)
    eur_jpy = round(1 / data["rates"]["EUR"], 2)
    return usd_jpy, eur_jpy


def get_emaxis_slim_price() -> int | None:
    """
    minkabu 投資信託 から eMAXIS Slim の基準価額を取得する。
    """
    url = f"https://itf.minkabu.jp/fund/{EMAXIS_SLIM_CODE}"
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }
    resp = requests.get(url, headers=headers, timeout=10)
    resp.raise_for_status()

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
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }
    resp = requests.get(url, headers=headers, timeout=10)
    resp.raise_for_status()

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


def send_slack(webhook_url: str, message: str) -> None:
    resp = requests.post(webhook_url, json={"text": message}, timeout=10)
    resp.raise_for_status()


def main() -> None:
    webhook_url = os.environ.get("SLACK_WEBHOOK_URL")
    if not webhook_url:
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

    # --- eMAXIS Slim 取得 ---
    try:
        price = get_emaxis_slim_price()
        if price:
            fund_text = f"• eMAXIS Slim 全世界株式（オール・カントリー）: *{price:,} 円*"
        else:
            fund_text = "• eMAXIS Slim: 基準価額を取得できませんでした"
    except Exception as e:
        errors.append(f"投資信託取得エラー: {e}")
        fund_text = "• 取得に失敗しました"

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
        f"📊 *本日の市場情報* ({date_str})\n"
        f"\n"
        f"🚃 *運行情報*\n{train_text}\n"
        f"\n"
        f"💱 *為替レート*\n{fx_text}\n"
        f"\n"
        f"📈 *投資信託（前営業日基準価額）*\n{fund_text}"
    )
    if errors:
        message += "\n\n⚠️ *エラー*\n" + "\n".join(f"• {e}" for e in errors)

    send_slack(webhook_url, message)
    print("Slack 通知を送信しました。")
    print(message)


if __name__ == "__main__":
    main()
