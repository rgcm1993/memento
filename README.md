# Memento

Reminders inside Telegram. Free up to 3 active, unlimited with Premium (Telegram Stars). Refer a friend and earn Premium.

- **Bot:** [@MementoPro_Bot](https://t.me/MementoPro_Bot)
- **Landing:** https://rgcm1993.github.io/memento/
- **Language:** Python 3 stdlib only (urllib + sqlite3 + threading) — zero dependencies.

## Features

- `/nuevo cuando texto` — e.g. `/nuevo mañana 09:30 llamar al banco`
  - Formats: `hoy 18:00`, `mañana 09:30`, `20-08 12:00`, `2026-12-31 23:59`
- `/lista`, `/hoy`, `/borrar <id>`, `/help`
- `/premium` — unlimited reminders for 100 ⭐ / 30 days, paid with Telegram Stars
- `/compartir` — referral link; each new user grants the inviter 30 days of Premium (max 10)
- Admin commands (hidden): `/stats`, `/invoice-test`

## Monetization

- Free tier: 3 active reminders
- Premium: unlimited for 100 ⭐ per 30 days (Telegram Stars, currency `XTR`)
- Referrals: +30 days Premium per invited friend (max 10)
- Payout: Stars are redeemed via the Telegram Wallet (min ~1000 ⭐)

## Architecture

- Single process, stdlib only
- `poller` thread ingests updates into a queue
- 3 `worker` threads process in parallel (each with its own sqlite connection, `PRAGMA busy_timeout=5000`)
- `ticker` thread fires due reminders every 10 s (independent of the poller)
- sqlite in WAL mode
- DNS resilience: resolves `api.telegram.org` once and caches the IP (TTL 600 s), so intermittent DNS failures don't block the bot
- `getMe` startup with 30 retries

## Run

```sh
# requirements (untracked):
echo 'YOUR_BOT_TOKEN' > bot/token.txt      # from @BotFather
echo 'YOUR_ADMIN_ID'  > bot/admin.txt      # or export ADMIN_ID
chmod 600 bot/token.txt bot/admin.txt

python3 bot/bot.py
```

Supervise with `supervisor.sh` (restarts the bot every 30 s if it dies).

## Why

A learning project: a self-hosted freemium Telegram bot with payments, referrals and a resilient network layer — all in pure Python stdlib, runnable on low-end hardware.
