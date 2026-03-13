# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Python script that runs daily via GitHub Actions (UTC 22:00 = JST 7:00) to send market and transit information to Slack. There is no build system or test framework — just a single script and a workflow.

## Running Locally

```bash
pip install -r requirements.txt
SLACK_WEBHOOK_URL="https://hooks.slack.com/..." python fetch_market.py
```

## Architecture

`fetch_market.py` fetches three data sources in sequence, then POSTs a combined message to Slack via Incoming Webhook:

1. **Exchange rates** — `frankfurter.app` REST API (no auth required), USD/JPY and EUR/JPY
2. **Fund price** — Web scraping `minkabu.jp` for eMAXIS Slim 全世界株式 (`0331418A`) using BeautifulSoup; returns previous business day's 基準価額
3. **Train status** — Web scraping `transit.yahoo.co.jp/traininfo/area/4/` for three Tokyo lines (三田線, 京浜東北線, 小田急線); Odakyu's three branches are consolidated into one entry

Each fetch is in its own try/except so a single failure doesn't block the rest of the notification.

## Deployment

The GitHub Actions workflow (`.github/workflows/daily_market.yml`) reads `SLACK_WEBHOOK_URL` from GitHub Secrets. See `DEPLOY.md` for setup steps.

## Collaboration Rules

- Before starting any implementation, always present a plan and get agreement.
- After presenting the plan, always ask "実装しますか？" and only proceed if the user answers "はい".

## Key Caveats

- Fund prices are scraped values and reflect the previous business day, not real-time
- HTML scraping logic will break if minkabu.jp or Yahoo路線情報 change their page structure
- User-Agent is set to an honest bot identifier (not a browser spoof)
