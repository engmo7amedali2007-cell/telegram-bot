# Telegram Username Scanner Pro — Setup Guide

## Requirements
- Python 3.10+
- pip install -r requirements.txt

## Environment Variables
Create a `.env` file:
```
BOT_TOKEN=your_telegram_bot_token
ADMIN_ID=your_telegram_user_id
USE_PROXIES=false
MAX_WORKERS=5
RATE_LIMIT=30
USE_FRAGMENT_API=true
CONFIRM_WITH_TME=true
```

## Running
```bash
cd bot
python bot.py
```

## How detection works (v2)

### Method 1 — Fragment.com JSON API (primary, fast)
Queries `https://fragment.com/username/check?username=<name>`
Returns: available / taken / sold / reserved / invalid
- No cookies required
- Most accurate source (uses Telegram's own auction database)
- Fast (~300ms per check)

### Method 2 — t.me HTML scrape (fallback + confirmation)
Used when Fragment API fails, AND to confirm AVAILABLE results from Fragment.
Looks for:
- TAKEN signals: `tgme_page_photo`, `tgme_page_extra`, `tgme_action_button`,
  "send message", "join channel", "subscribers", etc.
- AVAILABLE: `tgme_page_icon` present with NO taken signals

### Method 3 — Retry pass
After the main scan, all UNKNOWN results (network errors, Cloudflare blocks)
are retried once after a cool-off period (default 3s).

## Pattern syntax
- `$` = one letter (a-z)
- `#` = one digit (0-9)
- `_` = underscore
- Any other character = literal

Examples: `test$$`, `user####`, `$_#_$`
