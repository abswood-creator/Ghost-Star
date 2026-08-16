"""
Ghost Hunter — Telegram bot (commands) + entry point for the Mini App.

The Mini App itself is served by webapp.py. This file only handles chat commands.
Both share game.py and the same SQLite database.
"""

from __future__ import annotations

import logging
import os

from telegram import Update, WebAppInfo, MenuButtonWebApp
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from game import (
    GHOSTS,
    DECAY_AFTER_DAYS,
    get_db,
    init_db,
    get_or_create_player,
    save_player,
    log_practice,
    make_bar,
    player_status,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("ghost_hunter")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    conn = get_db()
    get_or_create_player(conn, update.effective_user.id, update.effective_user.first_name or "")
    conn.close()

    mini_app_url = os.environ.get("MINI_APP_URL", "").rstrip("/")
    extra = ""
    if mini_app_url:
        extra = (
            "\n\nOr open the *Mini App* with the menu button (bottom-left) "
            "to fight ghosts with the full cards."
        )

    text = (
        "🎸👻 *Ghost Hunter*\n\n"
        "Every time you finish practicing, log it with /practice. "
        "Each session chips away at whatever ghost is currently haunting your room.\n\n"
        f"Go quiet for more than {DECAY_AFTER_DAYS} days and it claws a little ground back "
        "— so a steady streak matters more than a big push.\n\n"
        "Commands:\n"
        "/practice — log a session, damage the current ghost\n"
        "/status — see your progress\n"
        "/ghosts — see the full roster\n"
        "/app — open the Mini App (if configured)"
        f"{extra}\n\n"
        f"First up: {GHOSTS[0]['emoji']} {GHOSTS[0]['name']}, the tiny electric ghost. Good luck."
    )
    await update.message.reply_text(text, parse_mode="Markdown")


async def practice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    conn = get_db()
    player = get_or_create_player(
        conn, update.effective_user.id, update.effective_user.first_name or ""
    )
    player, lines, _event = log_practice(conn, player)
    save_player(conn, player)
    conn.close()
    await update.message.reply_text("\n".join(lines))


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    conn = get_db()
    player = get_or_create_player(
        conn, update.effective_user.id, update.effective_user.first_name or ""
    )
    conn.close()

    st = player_status(player)
    if st["all_clear"]:
        await update.message.reply_text(
            "🏆 All 5 ghosts banished!\n"
            f"🎯 Total reps: {st['total_reps']}\n"
            f"🔥 Streak: {st['streak_days']} day(s)"
        )
        return

    g = st["current_ghost"]
    text = (
        f"{g['emoji']} {g['name']} — {g['subtitle']}\n"
        f"{g['bar']}  {g['progress']}/{g['reps_needed']}\n\n"
        f"🔥 Streak: {st['streak_days']} day(s)\n"
        f"🎯 Total reps: {st['total_reps']}\n"
        f"👻 Ghosts banished: {st['ghosts_defeated']}"
    )
    await update.message.reply_text(text)


async def ghosts_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lines = ["👻 *The Roster*\n"]
    for i, g in enumerate(GHOSTS, start=1):
        lines.append(f"{i}. {g['emoji']} {g['name']} — _{g['subtitle']}_")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def app_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a button that opens the Mini App."""
    mini_app_url = os.environ.get("MINI_APP_URL", "").rstrip("/")
    if not mini_app_url:
        await update.message.reply_text(
            "Mini App URL is not configured yet. Set MINI_APP_URL on the server "
            "(your Railway public domain)."
        )
        return

    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("Open Ghost Hunter", web_app=WebAppInfo(url=mini_app_url))]]
    )
    await update.message.reply_text(
        "Tap below to open the Mini App and fight the current ghost with its full card.",
        reply_markup=keyboard,
    )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Unhandled exception", exc_info=context.error)


async def post_init(application) -> None:
    """Set the chat menu button to the Mini App when MINI_APP_URL is present."""
    mini_app_url = os.environ.get("MINI_APP_URL", "").rstrip("/")
    if not mini_app_url:
        logger.info("MINI_APP_URL not set — skipping menu button configuration")
        return
    try:
        await application.bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(
                text="Hunt Ghosts",
                web_app=WebAppInfo(url=mini_app_url),
            )
        )
        logger.info("Chat menu button set to Mini App: %s", mini_app_url)
    except Exception as e:
        logger.warning("Could not set menu button: %s", e)


def build_application(token: str):
    app = ApplicationBuilder().token(token).post_init(post_init).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("practice", practice))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("ghosts", ghosts_cmd))
    app.add_handler(CommandHandler("app", app_cmd))
    app.add_error_handler(error_handler)
    return app


def main() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise SystemExit(
            "Set the TELEGRAM_BOT_TOKEN environment variable before running (see README.md)."
        )

    init_db()
    app = build_application(token)
    logger.info("Ghost Hunter bot starting (polling)...")
    app.run_polling()


if __name__ == "__main__":
    main()
