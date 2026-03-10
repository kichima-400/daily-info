"""
毎朝 JST 7:00 に実行され、以下の情報を Slack に通知する。
- ドル円レート
- ユーロ円レート
- eMAXIS Slim 全世界株式（オール・カントリー）基準価額
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

    # 方法1: <td> / <dd> などで "基準価額" ラベルの直後の数値要素を探す
    for tag in soup.find_all(string=re.compile("基準価額")):
        parent = tag.parent
        for sibling in parent.find_next_siblings():
            text = sibling.get_text(strip=True).replace(",", "").replace("円", "").strip()
            if re.fullmatch(r"\d+", text):
                return int(text)

    # 方法2: ページ全体テキストから「基準価額」直後の数値パターンを抽出
    page_text = soup.get_text()
    matches = re.findall(r"基準価額[^\d]{0,20}([\d,]+)", page_text)
    if matches:
        return int(matches[0].replace(",", ""))

    return None


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

    # --- Slack メッセージ構築 ---
    message = (
        f"📊 *本日の市場情報* ({date_str})\n"
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
