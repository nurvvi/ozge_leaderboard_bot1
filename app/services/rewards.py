from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import aiosqlite

from app.database import connect


@dataclass
class AwardResult:
    awarded: bool
    new_balance: int
    transaction_id: int | None = None
    reason: str | None = None


async def _ensure_user(db: aiosqlite.Connection, telegram_user_id: int, username: str | None, first_name: str) -> None:
    await db.execute(
        """INSERT INTO users(user_id,telegram_id,username,first_name,points,activity_points,coins,ozgecoins)
        VALUES(?,?,?,?,0,0,0,0)
        ON CONFLICT(user_id) DO UPDATE SET telegram_id=excluded.telegram_id,
        username=COALESCE(excluded.username,users.username),
        first_name=CASE WHEN excluded.first_name<>'' THEN excluded.first_name ELSE users.first_name END,
        updated_at=CURRENT_TIMESTAMP""",
        (telegram_user_id, telegram_user_id, username, first_name),
    )


async def award_in_transaction(
    db: aiosqlite.Connection,
    telegram_user_id: int,
    amount: int,
    event_type: str,
    reason: str,
    unique_key: str,
    *,
    username: str | None = None,
    first_name: str = "",
    chat_id: int | None = None,
    topic_id: int | None = None,
    source_message_id: int | None = None,
    admin_id: int | None = None,
    metadata: dict | None = None,
) -> AwardResult:
    await _ensure_user(db, telegram_user_id, username, first_name)
    current = (await (await db.execute("SELECT ozgecoins FROM users WHERE telegram_id=?", (telegram_user_id,))).fetchone())[0]
    effective = max(-current, amount)
    payload = dict(metadata or {})
    if effective != amount:
        payload["requested_amount"] = amount
    try:
        cursor = await db.execute(
            """INSERT INTO ozgecoin_transactions(telegram_user_id,amount,event_type,reason,unique_key,chat_id,topic_id,source_message_id,admin_id,metadata_json)
            VALUES(?,?,?,?,?,?,?,?,?,?)""",
            (telegram_user_id, effective, event_type, reason, unique_key, chat_id, topic_id, source_message_id, admin_id, json.dumps(payload, ensure_ascii=False)),
        )
    except aiosqlite.IntegrityError:
        return AwardResult(False, current, reason="duplicate")
    await db.execute("UPDATE users SET ozgecoins=ozgecoins+?,updated_at=CURRENT_TIMESTAMP WHERE telegram_id=?", (effective, telegram_user_id))
    balance = (await (await db.execute("SELECT ozgecoins FROM users WHERE telegram_id=?", (telegram_user_id,))).fetchone())[0]
    return AwardResult(True, balance, cursor.lastrowid)


async def award_ozgecoins(
    db_path: str | Path,
    telegram_user_id: int,
    amount: int,
    event_type: str,
    reason: str,
    *,
    unique_key: str,
    username: str | None = None,
    first_name: str = "",
    chat_id: int | None = None,
    topic_id: int | None = None,
    source_message_id: int | None = None,
    admin_id: int | None = None,
    metadata: dict | None = None,
    **_: object,
) -> AwardResult:
    async with connect(db_path) as db:
        await db.execute("BEGIN IMMEDIATE")
        result = await award_in_transaction(
            db, telegram_user_id, amount, event_type, reason, unique_key,
            username=username, first_name=first_name, chat_id=chat_id, topic_id=topic_id,
            source_message_id=source_message_id, admin_id=admin_id, metadata=metadata,
        )
        if result.awarded:
            await db.commit()
        else:
            await db.rollback()
        return result
