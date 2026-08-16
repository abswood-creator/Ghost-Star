# Ghost Hunter — Telegram bot

Turns practice sessions into a ghost hunt. `/practice` logs a session and
damages whichever of the 5 ghosts is currently haunting the player's room.
Miss more than a couple of days and the ghost claws back some progress, so
steady beats sporadic.

Roster, in order: Sparky → The Bed Crawler → The Window Stalker →
Red-Aura Wraith → Rockstar Specter (final boss, two-phase fight).

## What you actually need to do

Everything else is written — this is genuinely the whole list.

### 1. Get a bot token (2 minutes)
1. Open Telegram, message **@BotFather**.
2. Send `/newbot`, pick a name and a username (must end in `bot`).
3. BotFather replies with a token that looks like `123456789:AAExxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`. Copy it.

### 2. Run it somewhere
Locally, to try it out:
```bash
pip install -r requirements.txt
export TELEGRAM_BOT_TOKEN="paste your token here"
python bot.py
```
(On Windows, use `set TELEGRAM_BOT_TOKEN=...` instead of `export`.)

The bot uses **polling**, not a webhook, so it doesn't need a public URL —
it just needs to keep running. That means it'll not just work on your own
laptop as long as it's on, but also on any plain Python host.

For something that stays up when your laptop's closed, look at a small
always-on host — Railway, Render, Fly.io, or a cheap VPS are common choices
for a bot this size. Check each one's current free/hobby tier yourself,
since those change. Whichever you pick, the steps are the same:
- Set `TELEGRAM_BOT_TOKEN` as an environment variable in that host's dashboard.
- Point it at `python bot.py` (or `python3 bot.py`) as the start command.
- Requires Python 3.10+.

One thing to watch for: this bot stores progress in a local SQLite file
(`ghost_hunter.db`). Some free hosting tiers wipe the filesystem on every
redeploy, which would reset everyone's progress. If that happens, look for
a host with a persistent disk/volume, or ask me to swap in a hosted
database later — it's a small change.

## Commands
- `/start` — intro
- `/practice` — log a session
- `/status` — current ghost, progress bar, streak
- `/ghosts` — the full roster

## What I couldn't test
I don't have network access in this environment, so I couldn't actually
install `python-telegram-bot` or run this against Telegram's real API —
I checked the syntax compiles cleanly and wrote it against the current
(v22.8) library docs, but you'll be the first to actually run it. If
something breaks on first run, paste me the error and I'll fix it.

## Natural next additions
Not built yet, but straightforward to add on request: per-instrument
logging, a `/leaderboard` across friends, reminders if a streak's about
to lapse, inline buttons instead of typed commands.
