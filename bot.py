"""
Ghost Hunter — a Telegram bot that turns practice sessions into a ghost-hunt.

Every /practice logged chips away at whichever ghost currently haunts the
player's room. Clear all 5 — Sparky, The Bed Crawler, The Window Stalker,
Red-Aura Wraith, and the final boss Rockstar Specter — and the room's quiet.

Setup: see README.md. Requires TELEGRAM_BOT_TOKEN as an environment variable.
"""

import logging
import os
import sqlite3
from datetime import date, timedelta

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("ghost_hunter")

DB_PATH = os.environ.get("GHOST_HUNTER_DB", "ghost_hunter.db")
DECAY_AFTER_DAYS = 2   # go quiet longer than this and the ghost claws back a rep
DECAY_AMOUNT = 1
BAR_LENGTH = 10

GHOSTS = [
    {
        "name": "Sparky",
        "subtitle": "Tiny Electric Ghost",
        "emoji": "⚡",
        "reps_needed": 5,
        "victory_line": "Sparky's charge drops to zero and blinks out. Ghost banished!",
    },
    {
        "name": "The Bed Crawler",
        "subtitle": "Under-Bed Dweller",
        "emoji": "🛏️",
        "reps_needed": 6,
        "victory_line": "Pushed back into the dark for good. Back under the bed.",
    },
    {
        "name": "The Window Stalker",
        "subtitle": "Rain-Streaked Watcher",
        "emoji": "🌧️",
        "reps_needed": 6,
        "victory_line": "The glass fogs over completely. Gone from the window.",
    },
    {
        "name": "Red-Aura Wraith",
        "subtitle": "Wreathed in Red",
        "emoji": "🔥",
        "reps_needed": 5,
        "victory_line": "The last ember of its aura goes dark. The fire goes out.",
    },
    {
        "name": "Rockstar Specter",
        "subtitle": "Final Boss",
        "emoji": "🎸",
        "reps_needed": 9,
        "encore_at": 5,
        "victory_line": "One final chord rings out, then silence. Final bow.",
    },
]


# ---------- storage ----------

def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_db()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS players (
            user_id INTEGER PRIMARY KEY,
            first_name TEXT,
            ghost_index INTEGER NOT NULL DEFAULT 0,
            progress INTEGER NOT NULL DEFAULT 0,
            streak_days INTEGER NOT NULL DEFAULT 0,
            total_reps INTEGER NOT NULL DEFAULT 0,
            ghosts_defeated INTEGER NOT NULL DEFAULT 0,
            last_practice_date TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def get_or_create_player(conn: sqlite3.Connection, user_id: int, first_name: str) -> dict:
    row = conn.execute("SELECT * FROM players WHERE user_id = ?", (user_id,)).fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO players (user_id, first_name) VALUES (?, ?)",
            (user_id, first_name),
        )
        conn.commit()
        row = conn.execute("SELECT * FROM players WHERE user_id = ?", (user_id,)).fetchone()
    return dict(row)


def save_player(conn: sqlite3.Connection, player: dict) -> None:
    conn.execute(
        """
        UPDATE players SET
            first_name = ?, ghost_index = ?, progress = ?, streak_days = ?,
            total_reps = ?, ghosts_defeated = ?, last_practice_date = ?
        WHERE user_id = ?
        """,
        (
            player["first_name"],
            player["ghost_index"],
            player["progress"],
            player["streak_days"],
            player["total_reps"],
            player["ghosts_defeated"],
            player["last_practice_date"],
            player["user_id"],
        ),
    )
    conn.commit()


def make_bar(current: int, total: int, length: int = BAR_LENGTH) -> str:
    filled = round((current / total) * length) if total else 0
    filled = max(0, min(length, filled))
    return "▓" * filled + "░" * (length - filled)


# ---------- handlers ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    conn = get_db()
    get_or_create_player(conn, update.effective_user.id, update.effective_user.first_name)
    conn.close()

    text = (
        "🎸👻 *Ghost Hunter*\n\n"
        "Every time you finish practicing, log it with /practice. "
        "Each session chips away at whatever ghost is currently haunting your room.\n\n"
        f"Go quiet for more than {DECAY_AFTER_DAYS} days and it claws a little ground back "
        "— so a steady streak matters more than a big push.\n\n"
        "Commands:\n"
        "/practice — log a session, damage the current ghost\n"
        "/status — see your progress\n"
        "/ghosts — see the full roster\n\n"
        f"First up: {GHOSTS[0]['emoji']} {GHOSTS[0]['name']}, the tiny electric ghost. Good luck."
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def practice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    conn = get_db()
    player = get_or_create_player(conn, update.effective_user.id, update.effective_user.first_name)

    if player["ghost_index"] >= len(GHOSTS):
        await update.message.reply_text(
            "🏆 All 5 ghosts are already banished — your practice room is clear. Nice work."
        )
        conn.close()
        return

    today = date.today()
    last = date.fromisoformat(player["last_practice_date"]) if player["last_practice_date"] else None
    lines = []

    if last is not None:
        gap = (today - last).days
        if gap > DECAY_AFTER_DAYS and player["progress"] > 0:
            player["progress"] = max(0, player["progress"] - DECAY_AMOUNT)
            lines.append(f"It's been {gap} days — the ghost clawed back a little ground.\n")

    if last == today:
        pass
    elif last == today - timedelta(days=1):
        player["streak_days"] += 1
    else:
        player["streak_days"] = 1

    player["last_practice_date"] = today.isoformat()
    player["total_reps"] += 1
    player["progress"] += 1

    ghost = GHOSTS[player["ghost_index"]]
    lines.append(f"{ghost['emoji']} {ghost['name']}: {player['progress']}/{ghost['reps_needed']}")

    if ghost.get("encore_at") and player["progress"] == ghost["encore_at"]:
        lines.append("\n🎤 It staggers... then surges back for an ENCORE!")

    if player["progress"] >= ghost["reps_needed"]:
        lines.append(f"\n{ghost['victory_line']}")
        player["ghosts_defeated"] += 1
        player["ghost_index"] += 1
        player["progress"] = 0

        if player["ghost_index"] >= len(GHOSTS):
            lines.append("\n🏆 That's all 5. The practice room is finally quiet — nice work.")
        else:
            nxt = GHOSTS[player["ghost_index"]]
            lines.append(f"\nNext up: {nxt['emoji']} {nxt['name']} — {nxt['subtitle']}")

    save_player(conn, player)
    conn.close()
    await update.message.reply_text("\n".join(lines))


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    conn = get_db()
    player = get_or_create_player(conn, update.effective_user.id, update.effective_user.first_name)
    conn.close()

    if player["ghost_index"] >= len(GHOSTS):
        await update.message.reply_text(
            "🏆 All 5 ghosts banished!\n"
            f"🎯 Total reps: {player['total_reps']}\n"
            f"🔥 Streak: {player['streak_days']} day(s)"
        )
        return

    ghost = GHOSTS[player["ghost_index"]]
    bar = make_bar(player["progress"], ghost["reps_needed"])
    text = (
        f"{ghost['emoji']} {ghost['name']} — {ghost['subtitle']}\n"
        f"{bar}  {player['progress']}/{ghost['reps_needed']}\n\n"
        f"🔥 Streak: {player['streak_days']} day(s)\n"
        f"🎯 Total reps: {player['total_reps']}\n"
        f"👻 Ghosts banished: {player['ghosts_defeated']}"
    )
    await update.message.reply_text(text)


async def ghosts_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lines = ["👻 *The Roster*\n"]
    for i, g in enumerate(GHOSTS, start=1):
        lines.append(f"{i}. {g['emoji']} {g['name']} — _{g['subtitle']}_")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Unhandled exception", exc_info=context.error)


def main() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit(
            "Set the TELEGRAM_BOT_TOKEN environment variable before running (see README.md)."
        )

    init_db()

    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("practice", practice))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("ghosts", ghosts_cmd))
    app.add_error_handler(error_handler)

    logger.info("Ghost Hunter bot starting (polling)...")
    app.run_polling()


if __name__ == "__main__":
    main()
