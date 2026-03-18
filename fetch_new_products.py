"""
毎日 JST 11:30 に実行され、mdingon.com の新商品人気ランキングを Slack に通知する。
データは毎朝 10:00 JST 更新のため、11:30 実行で最新データを取得できる。
"""

import os
import re
import sys
import unicodedata
import urllib.parse
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

JST = ZoneInfo("Asia/Tokyo")
TIMEOUT = 20
RANKING_URL = "https://www.mdingon.com/"
HEADERS = {"User-Agent": "fetch-market-bot/1.0"}

TREND_EMOJI = {
    "NEW":  "🆕",
    "UP":   "📈",
    "DOWN": "📉",
    "-":    "➡️",
}


def get_new_product_ranking() -> tuple[str, list[dict]]:
    """
    mdingon.com から新商品人気ランキングを取得する。
    戻り値: (ランキング日付文字列, items リスト)
    items の各要素: {"rank": int, "trend": str, "name": str, "jan_code": str, "maker": str}
    """
    resp = requests.get(RANKING_URL, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")

    # 「毎日更新！今売れている話題の新商品」を含む見出しを探す
    heading = None
    for tag in soup.find_all(["h2", "h3", "h4"]):
        if "今売れている" in tag.get_text() or "新商品" in tag.get_text():
            heading = tag
            break

    if heading is None:
        raise ValueError("新商品ランキングの見出しが見つかりませんでした")

    # 見出し直後の <p>（ランキング日付）と <table> を取得
    ranking_date_str = ""
    table = None
    for sibling in heading.find_next_siblings():
        tag_name = sibling.name
        if tag_name == "p" and not ranking_date_str:
            text = sibling.get_text(strip=True)
            # 例: "2026年3月16日（月） RDSランキング"
            m = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", text)
            if m:
                y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
                ranking_date_str = f"{y}-{mo:02d}-{d:02d}"
        elif tag_name == "table":
            table = sibling
            break
        elif tag_name in ("h2", "h3", "h4"):
            # 別の見出しに入ったら停止
            break

    if table is None:
        raise ValueError("新商品ランキングのテーブルが見つかりませんでした")

    items = []
    for tr in table.find_all("tr"):
        tds = tr.find_all("td")
        if len(tds) < 5:
            continue

        # 順位・変動は <img alt="1位"> / <img alt="NEW"> 形式
        rank_img  = tds[0].find("img")
        trend_img = tds[1].find("img")
        rank_text  = rank_img["alt"]  if rank_img  else tds[0].get_text(strip=True)
        trend_text = trend_img["alt"] if trend_img else tds[1].get_text(strip=True)

        name_text  = _normalize_kana(tds[2].get_text(strip=True))
        jan_text   = tds[3].get_text(strip=True)
        maker_text = tds[4].get_text(strip=True)

        m = re.match(r"(\d+)位", rank_text)
        if not m:
            continue

        items.append({
            "rank":     int(m.group(1)),
            "trend":    trend_text,
            "name":     name_text,
            "jan_code": jan_text,
            "maker":    maker_text,
        })

    if not items:
        raise ValueError("ランキングデータが取得できませんでした")

    return ranking_date_str, items


def _normalize_kana(text: str) -> str:
    """半角カタカナを全角カタカナに変換する。"""
    result = []
    for ch in text:
        code = ord(ch)
        # 半角カタカナ: U+FF65〜U+FF9F
        if 0xFF65 <= code <= 0xFF9F:
            result.append(unicodedata.normalize("NFKC", ch))
        else:
            result.append(ch)
    return "".join(result)


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

    # --- ランキング取得 ---
    try:
        ranking_date, items = get_new_product_ranking()
        date_label = f"{ranking_date} 時点" if ranking_date else "日付不明"

        def glink(query: str, label: str) -> str:
            url = "https://www.google.com/search?q=" + urllib.parse.quote_plus(query)
            return f"<{url}|{label}>"

        lines = []
        for item in items:
            emoji = TREND_EMOJI.get(item["trend"], "ℹ️")
            name_link  = glink(item["name"],     item["name"])
            maker_link = glink(item["maker"],    item["maker"])
            jan_part = (
                f" | JAN: {glink(item['jan_code'], item['jan_code'])}"
                if item["jan_code"] else ""
            )
            lines.append(
                f"{item['rank']}位 {emoji} *{name_link}*\n"
                f"   {maker_link}{jan_part}"
            )
        ranking_text = "\n".join(lines)
    except Exception as e:
        errors.append(f"ランキング取得エラー: {e}")
        ranking_text = "• 取得に失敗しました"
        date_label = ""

    # --- Slack メッセージ構築 ---
    header = f"🆕 *新商品人気ランキング* ({date_str})"
    if date_label:
        header += f"\nRDSランキング（{date_label}）"

    message = f"{header}\n\n{ranking_text}"

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
