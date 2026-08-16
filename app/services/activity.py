from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.config import Settings, in_flood_scope
from app.database import connect
from app.services.rewards import AwardResult, award_ozgecoins


MEANINGFUL_RE = re.compile(r"[A-Za-zА-Яа-яЁёӘәҒғҚқҢңӨөҰұҮүҺһІі0-9]")


@dataclass
class ActivityInput:
    user_id: int
    chat_id: int
    topic_id: int | None
    message_id: int
    username: str | None = None
    first_name: str = ""
    text: str | None = None
    content_type: str = "text"
    is_bot: bool = False
    is_forwarded: bool = False
    is_service: bool = False


def normalize_text(text: str) -> str:
    return " ".join(text.casefold().split())


def is_meaningful_text(text: str | None, minimum: int) -> bool:
    if not text or text.lstrip().startswith("/"):
        return False
    return len(MEANINGFUL_RE.findall(text)) >= minimum


def passive_points(item: ActivityInput, settings: Settings) -> int:
    if item.is_bot or item.is_forwarded or item.is_service:
        return 0
    if not in_flood_scope(item.chat_id, item.topic_id, settings):
        return 0
    if item.content_type == "text":
        return settings.text_points if is_meaningful_text(item.text, settings.min_meaningful_text_length) else 0
    return {"photo": settings.photo_points, "video": settings.video_points, "voice": settings.voice_points, "video_note": settings.video_note_points}.get(item.content_type, 0)


async def process_activity(db_path: str | Path, item: ActivityInput, settings: Settings) -> AwardResult:
    points = passive_points(item, settings)
    if not points:
        return AwardResult(False, 0, reason="ineligible")
    normalized = normalize_text(item.text or "") or None
    cutoff = (datetime.now(timezone.utc) - timedelta(seconds=settings.message_cooldown_seconds)).strftime("%Y-%m-%d %H:%M:%S")
    today = datetime.now(timezone.utc).date().isoformat()
    async with connect(db_path) as db:
        duplicate_id = await (await db.execute("SELECT 1 FROM processed_messages WHERE chat_id=? AND message_id=?", (item.chat_id, item.message_id))).fetchone()
        if duplicate_id:
            return AwardResult(False, 0, reason="duplicate_message")
        if normalized:
            duplicate_text = await (await db.execute(
                "SELECT 1 FROM processed_messages WHERE user_id=? AND normalized_text=? AND processed_at>=? LIMIT 1",
                (item.user_id, normalized, cutoff),
            )).fetchone()
            if duplicate_text:
                return AwardResult(False, 0, reason="duplicate_text")
        passive_today = (await (await db.execute(
            "SELECT COALESCE(SUM(amount),0) FROM ozgecoin_transactions WHERE telegram_user_id=? AND event_type='passive_activity' AND date(created_at)=?",
            (item.user_id, today),
        )).fetchone())[0]
        allowed = max(0, min(points, settings.passive_daily_limit - passive_today))
        if not allowed:
            return AwardResult(False, 0, reason="daily_limit")
        await db.execute("INSERT INTO processed_messages(chat_id,message_id,user_id,normalized_text) VALUES(?,?,?,?)", (item.chat_id, item.message_id, item.user_id, normalized))
        await db.commit()
    result = await award_ozgecoins(
        db_path, item.user_id, allowed, "passive_activity", f"{item.content_type} activity",
        username=item.username, first_name=item.first_name, chat_id=item.chat_id, topic_id=item.topic_id,
        source_message_id=item.message_id, unique_key=f"message:{item.chat_id}:{item.message_id}", metadata={"content_type": item.content_type},
    )
    return result
