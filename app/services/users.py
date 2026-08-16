from __future__ import annotations

from html import escape
from pathlib import Path

from app.database import connect


async def get_top(db_path: str | Path, limit: int = 15) -> list[dict]:
    async with connect(db_path) as db:
        rows = await (await db.execute("SELECT user_id,telegram_id,username,first_name,ozgecoins FROM users ORDER BY ozgecoins DESC,user_id LIMIT ?", (limit,))).fetchall()
        return [dict(row) for row in rows]


async def get_profile(db_path: str | Path, user_id: int) -> dict | None:
    async with connect(db_path) as db:
        row = await (await db.execute(
            """SELECT u.*, (SELECT COUNT(*)+1 FROM users x WHERE x.ozgecoins>u.ozgecoins) rank
            FROM users u WHERE u.telegram_id=?""", (user_id,)
        )).fetchone()
        return dict(row) if row else None


async def upsert_user(db_path: str | Path, telegram_id: int, username: str | None, first_name: str) -> None:
    async with connect(db_path) as db:
        await db.execute(
            """INSERT INTO users(user_id,telegram_id,username,first_name,points,activity_points,coins,ozgecoins)
            VALUES(?,?,?,?,0,0,0,0)
            ON CONFLICT(user_id) DO UPDATE SET telegram_id=excluded.telegram_id,username=excluded.username,
            first_name=CASE WHEN excluded.first_name<>'' THEN excluded.first_name ELSE users.first_name END,updated_at=CURRENT_TIMESTAMP""",
            (telegram_id, telegram_id, username, first_name),
        )
        await db.commit()


def display_name(row: dict) -> str:
    if row.get("username"):
        return "@" + escape(str(row["username"]))
    return escape(str(row.get("first_name") or f"User {row['user_id']}"))


def render_top(rows: list[dict]) -> str:
    lines = ["🏆 <b>Көшбасшылар</b>", ""]
    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    for rank, row in enumerate(rows, 1):
        lines.append(f"{medals.get(rank, str(rank)+'.')} {display_name(row)} — <b>{row['ozgecoins']}</b> ÖZGEcoins")
    return "\n".join(lines) if rows else "🏆 Рейтинг пока пуст."
