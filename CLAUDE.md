@docs/spec.md


# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Two Python scripts run daily via GitHub Actions to send information to Slack:
- `fetch_market.py` — UTC 22:00 (JST 7:00): market rates, fund prices, rice price, train status
- `fetch_new_products.py` — UTC 02:30 (JST 11:30): new product popularity ranking from mdingon.com

There is no build system or test framework — just scripts and workflows.

## Running Locally

```bash
pip install -r requirements.txt
SLACK_WEBHOOK_URL="https://hooks.slack.com/..." python fetch_market.py
SLACK_WEBHOOK_URL="https://hooks.slack.com/..." python fetch_new_products.py
```

## Architecture

`fetch_market.py` fetches five data sources in sequence, then POSTs a combined message to Slack via Incoming Webhook:

1. **Exchange rates** — `frankfurter.app` REST API (no auth required), USD/JPY and EUR/JPY
2. **Fund price** — Web scraping `minkabu.jp` for three funds (全世界株式オルカン `0331418A`, 米国株式S&P500 `03311187`, バランス8資産均等型 `03312175`) using BeautifulSoup; returns previous business day's 基準価額
3. **Rice price** — `price-transition.mdingon.com` REST API (no auth required); returns the latest available date's 平均売価 (tax-exclusive) for 5kg rice
4. **Hormuz transit count** — IMF PortWatch ArcGIS REST API (no auth required); returns the last 7 days of daily vessel transit counts for the Strait of Hormuz (chokepoint6); updated weekly every Tuesday
5. **Train status** — Web scraping `transit.yahoo.co.jp/traininfo/area/4/` for five lines (三田線, 京浜東北線, 小田急線, 東急田園都市線, 京急本線); Odakyu's three branches are consolidated into one entry

`fetch_new_products.py` scrapes `www.mdingon.com` for the RDS new product ranking table and POSTs to Slack. Rank and trend values are stored in `<img alt="...">` attributes (not text). Half-width katakana in product names is normalized to full-width.

Each fetch is in its own try/except so a single failure doesn't block the rest of the notification.

If `DRY_RUN=true` is set, Slack sending is skipped and the message is printed to stdout instead.

## Deployment

Four workflows exist:
- `.github/workflows/daily_market.yml` — production, runs daily at UTC 22:00, reads `SLACK_WEBHOOK_URL` from GitHub Secrets
- `.github/workflows/dev_market.yml` — development, manual trigger only, sets `DRY_RUN=true`
- `.github/workflows/new_products.yml` — production, runs daily at UTC 02:30, reads `SLACK_WEBHOOK_URL` from GitHub Secrets
- `.github/workflows/dev_new_products.yml` — development, manual trigger only, sets `DRY_RUN=true`

See `DEPLOY.md` for setup steps.

## Collaboration Rules

- Before starting any implementation, always present a plan and get agreement.
- After presenting the plan, always ask "実装しますか？" and only proceed if the user answers "はい".
- Before any destructive operations (deletions, force push, etc.), always ask for confirmation.
- Only commit and push when explicitly requested by the user.

## Key Caveats

- Fund prices are scraped values and reflect the previous business day, not real-time
- Rice price is tax-exclusive (軽減税率8%対象); multiply by 1.08 for tax-inclusive estimate
- Rice price data is sourced from RDS-POS (株式会社マーチャンダイジング・オン), updated 3 times daily
- HTML scraping logic will break if minkabu.jp or Yahoo路線情報 change their page structure
- User-Agent is set to an honest bot identifier (not a browser spoof)
- Hormuz transit data is from IMF PortWatch (IMF / Oxford), updated weekly (Tuesdays JST 23:00); data may lag up to 7 days and can be affected by GPS jamming or AIS spoofing
