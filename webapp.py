"""
Ghost Hunter — FastAPI server for the Telegram Mini App + static cards.

Serves:
  /                 Mini App home (roster + current ghost + practice button)
  /card/{ghost_id}  Dedicated card page for that ghost (separate pages)
  /api/status       Player status (requires Telegram WebApp initData)
  /api/practice     Log one practice session

Also starts the Telegram bot (polling) in a background thread so one Railway
service can run both the web Mini App and the chat bot.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import threading
from pathlib import Path
from urllib.parse import parse_qsl

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from game import (
    GHOSTS,
    get_db,
    init_db,
    get_or_create_player,
    save_player,
    log_practice,
    player_status,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("ghost_hunter.web")

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="Ghost Hunter Mini App")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ---------- Telegram WebApp initData validation ----------

def validate_init_data(init_data: str, bot_token: str) -> dict:
    """Validate Telegram WebApp initData and return the parsed user dict.

    Raises HTTPException(401) on failure.
    """
    if not init_data or not bot_token:
        raise HTTPException(status_code=401, detail="Missing initData or bot token")

    parsed = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = parsed.pop("hash", None)
    if not received_hash:
        raise HTTPException(status_code=401, detail="Missing hash")

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    calculated = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(calculated, received_hash):
        raise HTTPException(status_code=401, detail="Invalid initData signature")

    user_raw = parsed.get("user")
    if not user_raw:
        raise HTTPException(status_code=401, detail="No user in initData")

    try:
        user = json.loads(user_raw)
    except json.JSONDecodeError:
        raise HTTPException(status_code=401, detail="Bad user JSON")

    return user


def get_user_from_request(
    x_telegram_init_data: str | None = Header(None),
    authorization: str | None = Header(None),
) -> dict:
    """Extract and validate the Telegram user from headers."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    init_data = x_telegram_init_data
    if not init_data and authorization and authorization.startswith("tma "):
        init_data = authorization[4:]
    user = validate_init_data(init_data or "", token)
    return user


# ---------- API ----------

@app.get("/api/status")
async def api_status(
    x_telegram_init_data: str | None = Header(None),
    authorization: str | None = Header(None),
):
    user = get_user_from_request(x_telegram_init_data, authorization)
    conn = get_db()
    player = get_or_create_player(conn, user["id"], user.get("first_name") or "")
    conn.close()
    return player_status(player)


@app.post("/api/practice")
async def api_practice(
    x_telegram_init_data: str | None = Header(None),
    authorization: str | None = Header(None),
):
    user = get_user_from_request(x_telegram_init_data, authorization)
    conn = get_db()
    player = get_or_create_player(conn, user["id"], user.get("first_name") or "")
    player, lines, event = log_practice(conn, player)
    save_player(conn, player)
    status = player_status(player)
    conn.close()
    return {
        "ok": True,
        "messages": lines,
        "event": {
            "encore": event["encore"],
            "all_clear": event["all_clear"],
            "defeated_ghost": (
                {
                    "id": event["defeated_ghost"]["id"],
                    "name": event["defeated_ghost"]["name"],
                    "emoji": event["defeated_ghost"]["emoji"],
                }
                if event["defeated_ghost"]
                else None
            ),
        },
        "status": status,
    }


@app.get("/api/health")
async def health():
    return {"ok": True, "service": "ghost-hunter"}


# ---------- Pages ----------

@app.get("/", response_class=HTMLResponse)
async def miniapp_home(request: Request):
    """Main Mini App entry — roster + current ghost + practice."""
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "ghosts": GHOSTS,
        },
    )


@app.get("/card/{ghost_id}", response_class=HTMLResponse)
async def ghost_card(request: Request, ghost_id: str):
    """Serve the original animated SVG card for this ghost, with Mini App bridge injected."""
    ghost = next((g for g in GHOSTS if g["id"] == ghost_id), None)
    if not ghost:
        raise HTTPException(status_code=404, detail="Unknown ghost")

    card_path = STATIC_DIR / "cards" / ghost["card"]
    if not card_path.is_file():
        # Fallback to simple template if the fancy card is missing
        return templates.TemplateResponse(
            "card.html",
            {"request": request, "ghost": ghost, "ghosts": GHOSTS},
        )

    html = card_path.read_text(encoding="utf-8")

    # Inject Telegram WebApp SDK + ghost id + bridge (hooks practice to the API)
    inject = (
        '\n<script src="https://telegram.org/js/telegram-web-app.js"></script>\n'
        f'<script>window.__GHOST_ID__ = "{ghost_id}";</script>\n'
        '<script src="/static/card-bridge.js"></script>\n'
    )
    if "</body>" in html:
        html = html.replace("</body>", inject + "</body>", 1)
    else:
        html = html + inject

    return HTMLResponse(content=html)


# ---------- Startup: DB + bot thread ----------

def _run_bot():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        logger.warning("TELEGRAM_BOT_TOKEN not set — bot will not start")
        return
    try:
        from bot import build_application

        application = build_application(token)
        logger.info("Starting Telegram bot (polling) in background thread...")
        application.run_polling(drop_pending_updates=True)
    except Exception:
        logger.exception("Bot thread crashed")


@app.on_event("startup")
async def on_startup():
    init_db()
    # Auto-set MINI_APP_URL from Railway if not provided
    if not os.environ.get("MINI_APP_URL"):
        railway_domain = os.environ.get("RAILWAY_PUBLIC_DOMAIN")
        if railway_domain:
            os.environ["MINI_APP_URL"] = f"https://{railway_domain}"
            logger.info("MINI_APP_URL set from RAILWAY_PUBLIC_DOMAIN: %s", os.environ["MINI_APP_URL"])

    # Start bot in background so one process serves web + bot
    if os.environ.get("DISABLE_BOT_THREAD", "").lower() not in ("1", "true", "yes"):
        t = threading.Thread(target=_run_bot, name="telegram-bot", daemon=True)
        t.start()
        logger.info("Bot thread launched")
