"""
Shared game logic and storage for Ghost Hunter.

Both bot.py (Telegram commands) and webapp.py (the Mini App API) import
from here, so a practice session logged through either one updates the
exact same player record the same way.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import date, timedelta
from typing import Any

DB_PATH = os.environ.get("GHOST_HUNTER_DB", "ghost_hunter.db")
DECAY_AFTER_DAYS = 2
DECAY_AMOUNT = 1
BAR_LENGTH = 10

GHOSTS: list[dict[str, Any]] = [
    {
        "id": "sparky",
        "name": "Sparky",
        "subtitle": "Tiny Electric Ghost",
        "emoji": "⚡",
        "reps_needed": 5,
        "victory_line": "Sparky's charge drops to zero and blinks out. Ghost banished!",
        "card": "sparky-ghost-card.html",
    },
    {
        "id": "bed-crawler",
        "name": "The Bed Crawler",
        "subtitle": "Under-Bed Dweller",
        "emoji": "🛏️",
        "reps_needed": 6,
        "victory_line": "Pushed back into the dark for good. Back under the bed.",
        "card": "bed-crawler-card.html",
    },
    {
        "id": "window-stalker",
        "name": "The Window Stalker",
        "subtitle": "Rain-Streaked Watcher",
        "emoji": "🌧️",
        "reps_needed": 6,
        "victory_line": "The glass fogs over completely. Gone from the window.",
        "card": "window-stalker-card.html",
    },
    {
        "id": "red-aura-wraith",
        "name": "Red-Aura Wraith",
        "subtitle": "Wreathed in Red",
        "emoji": "🔥",
        "reps_needed": 5,
        "victory_line": "The last ember of its aura goes dark. The fire goes out.",
        "card": "red-aura-wraith-card.html",
    },
    {
        "id": "rockstar-specter",
        "name": "Rockstar Specter",
        "subtitle": "Final Boss",
        "emoji": "🎸",
        "reps_needed": 9,
        "encore_at": 5,
        "victory_line": "One final chord rings out, then silence. Final bow.",
        "card": "rockstar-specter-card.html",
    },
]


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


def log_practice(conn: sqlite3.Connection, player: dict):
    """Apply one practice rep to a player.

    Returns (updated_player, message_lines, event) where event is
    {"encore": bool, "defeated_ghost": dict | None, "all_clear": bool}
    so callers (bot commands or the API) can react without re-deriving it.
    """
    event = {"encore": False, "defeated_ghost": None, "all_clear": False}

    if player["ghost_index"] >= len(GHOSTS):
        return player, ["🏆 All 5 ghosts are already banished — your practice room is clear."], event

    today = date.today()
    last = date.fromisoformat(player["last_practice_date"]) if player["last_practice_date"] else None
    lines: list[str] = []

    if last is not None:
        gap = (today - last).days
        if gap > DECAY_AFTER_DAYS and player["progress"] > 0:
            player["progress"] = max(0, player["progress"] - DECAY_AMOUNT)
            lines.append(f"It's been {gap} days — the ghost clawed back a little ground.")

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
        event["encore"] = True
        lines.append("🎤 It staggers... then surges back for an ENCORE!")

    if player["progress"] >= ghost["reps_needed"]:
        lines.append(ghost["victory_line"])
        event["defeated_ghost"] = ghost
        player["ghosts_defeated"] += 1
        player["ghost_index"] += 1
        player["progress"] = 0

        if player["ghost_index"] >= len(GHOSTS):
            event["all_clear"] = True
            lines.append("🏆 That's all 5. The practice room is finally quiet — nice work.")
        else:
            nxt = GHOSTS[player["ghost_index"]]
            lines.append(f"Next up: {nxt['emoji']} {nxt['name']} — {nxt['subtitle']}")

    return player, lines, event


def player_status(player: dict) -> dict:
    """Serialize a player row into a clean API / frontend payload."""
    idx = player["ghost_index"]
    all_clear = idx >= len(GHOSTS)
    current = None if all_clear else GHOSTS[idx]

    return {
        "user_id": player["user_id"],
        "first_name": player["first_name"],
        "ghost_index": idx,
        "progress": player["progress"],
        "streak_days": player["streak_days"],
        "total_reps": player["total_reps"],
        "ghosts_defeated": player["ghosts_defeated"],
        "last_practice_date": player["last_practice_date"],
        "all_clear": all_clear,
        "current_ghost": (
            None
            if all_clear
            else {
                "id": current["id"],
                "name": current["name"],
                "subtitle": current["subtitle"],
                "emoji": current["emoji"],
                "reps_needed": current["reps_needed"],
                "progress": player["progress"],
                "bar": make_bar(player["progress"], current["reps_needed"]),
                "card": current["card"],
                "encore_at": current.get("encore_at"),
            }
        ),
        "roster": [
            {
                "id": g["id"],
                "name": g["name"],
                "subtitle": g["subtitle"],
                "emoji": g["emoji"],
                "reps_needed": g["reps_needed"],
                "defeated": i < idx,
                "current": i == idx and not all_clear,
            }
            for i, g in enumerate(GHOSTS)
        ],
    }
