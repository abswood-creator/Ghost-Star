# Ghost Hunter — Telegram bot + Mini App

Turns practice sessions into a ghost hunt. `/practice` (or the Mini App button) logs a session and damages whichever of the 5 ghosts is currently haunting the player's room. Miss more than a couple of days and the ghost claws back some progress, so steady beats sporadic.

**Roster:** Sparky → The Bed Crawler → The Window Stalker → Red-Aura Wraith → Rockstar Specter (final boss, two-phase fight).

## What you need

1. A bot token from [@BotFather](https://t.me/BotFather)
2. This repo deployed on Railway (or any host that can run Python + expose HTTPS)

## Railway setup (already linked to this repo)

Your Railway service is already connected to the GitHub repo. After you push the new files:

### 1. Environment variables

In the Railway service → **Variables**, set:

| Variable | Required | Description |
|----------|----------|-------------|
| `TELEGRAM_BOT_TOKEN` | Yes | Token from BotFather |
| `MINI_APP_URL` | Recommended | Your public Railway URL, e.g. `https://your-service.up.railway.app` |
| `GHOST_HUNTER_DB` | Optional | Path for SQLite. Default: `ghost_hunter.db` |
| `PORT` | Auto | Railway sets this |

If you leave `MINI_APP_URL` empty, the app will try to use `RAILWAY_PUBLIC_DOMAIN` automatically.

### 2. Start command

Railway should detect the `Procfile`. If not, set the start command to:

```bash
uvicorn webapp:app --host 0.0.0.0 --port $PORT
```

This single process serves:

- The Mini App (web UI + API)
- The Telegram bot (polling in a background thread)

### 3. Persistent volume (important)

The bot stores progress in a local SQLite file. Railway’s ephemeral filesystem wipes on redeploy unless you attach a volume.

1. Railway project → your service → **Settings** → **Volumes**
2. Add a volume, mount path e.g. `/data`
3. Set variable: `GHOST_HUNTER_DB=/data/ghost_hunter.db`

### 4. Deploy

Push to `main`. Railway will rebuild and redeploy.

After deploy, open the public URL — you should see the Mini App home (roster). `/api/health` should return `{"ok":true}`.

### 5. BotFather — wire the Mini App

1. Open [@BotFather](https://t.me/BotFather)
2. `/setmenubutton` → select your bot  
   - URL: `https://YOUR-RAILWAY-DOMAIN` (same as `MINI_APP_URL`)  
   - Button text: `Hunt Ghosts` (or anything)
3. Optional but recommended: `/newapp` → create a Mini App linked to the bot with the same URL (gives you a `t.me/YourBot/app` link)
4. Optional: `/setdomain` → set the Railway domain so WebApp features work cleanly

The bot also tries to set the menu button automatically on startup when `MINI_APP_URL` is present.

## Commands (chat)

- `/start` — intro
- `/practice` — log a session
- `/status` — current ghost, progress bar, streak
- `/ghosts` — full roster
- `/app` — open Mini App button

## Mini App

- **Home (`/`)** — current ghost, progress bar, big “Log practice” button, full roster
- **Separate cards (`/card/sparky`, `/card/bed-crawler`, …)** — dedicated page per ghost  
  Practice only works on the ghost that is currently active for the player.

Progress is shared: a practice logged in the Mini App updates the same player record as `/practice` in chat.

## Local development

```bash
pip install -r requirements.txt
export TELEGRAM_BOT_TOKEN="your-token"
export MINI_APP_URL="https://your-ngrok-or-local-tunnel"   # optional for menu button
uvicorn webapp:app --host 0.0.0.0 --port 8000
```

For Telegram to open the Mini App you need HTTPS. Use [ngrok](https://ngrok.com/) or similar:

```bash
ngrok http 8000
# then set MINI_APP_URL to the https URL and update BotFather
```

To run only the bot (no web):

```bash
python bot.py
```

## Project layout

```
bot.py          # Telegram commands + menu button
game.py         # Shared logic + SQLite
webapp.py       # FastAPI Mini App + API + starts bot thread
templates/      # Mini App HTML (home + per-ghost cards)
Procfile        # Railway start command
requirements.txt
```

## Notes

- Python 3.10+
- Polling is used (no webhook required). One Railway service is enough.
- If the bot thread fails to start, check logs for `TELEGRAM_BOT_TOKEN` and network access to `api.telegram.org`.
