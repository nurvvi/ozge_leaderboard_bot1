from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from app.config import normalize_topic_id
from app.database import connect
from app.services.rewards import AwardResult, award_in_transaction

DATA_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "daily_tasks.json"


def load_daily_tasks(path: Path = DATA_PATH) -> list[dict]:
    tasks = json.loads(path.read_text(encoding="utf-8"))
    required = {"id", "type", "kk", "ru", "reward", "active"}
    for task in tasks:
        missing = required - task.keys()
        if missing:
            raise ValueError(f"Daily task {task.get('id','?')} is missing: {', '.join(sorted(missing))}")
    return tasks


def local_date(timezone_name: str, now: datetime | None = None) -> str:
    zone = ZoneInfo(timezone_name)
    local_now = now.astimezone(zone) if now and now.tzinfo else (now.replace(tzinfo=zone) if now else datetime.now(zone))
    return local_now.date().isoformat()


def get_daily_task(timezone_name: str = "Asia/Almaty", now: datetime | None = None, path: Path = DATA_PATH) -> dict:
    day = local_date(timezone_name, now)
    tasks = [item for item in load_daily_tasks(path) if item.get("active")]
    if not tasks:
        raise ValueError("No active daily tasks")
    index = datetime.fromisoformat(day).date().toordinal() % len(tasks)
    return {**tasks[index], "date": day}


def format_daily_task(task: dict) -> str:
    reward = int(task.get("reward", 0))
    reward_text = f"+{reward} ÖZGEcoins" if reward else "Автоматты марапат жоқ / Без автоматической награды"
    return (
        f"🌞 <b>Күн тапсырмасы</b>\n\n{task['kk']}\n\n"
        f"<b>Задание дня</b>\n\n{task['ru']}\n\n"
        f"<b>Reward:</b>\n{reward_text}"
    )


async def register_daily_task_post(db_path: str | Path, task: dict, chat_id: int, topic_id: int | None, telegram_message_id: int) -> None:
    async with connect(db_path) as db:
        await db.execute(
            """INSERT INTO daily_task_posts(task_id,task_date,chat_id,topic_id,telegram_message_id)
            VALUES(?,?,?,?,?) ON CONFLICT(task_date,chat_id,topic_id) DO UPDATE SET
            task_id=excluded.task_id,telegram_message_id=excluded.telegram_message_id,created_at=CURRENT_TIMESTAMP""",
            (task["id"], task["date"], chat_id, normalize_topic_id(topic_id), telegram_message_id),
        )
        await db.commit()


def _contains_word(text: str, word: str) -> bool:
    alphabet = r"\wӘәҒғҚқҢңӨөҰұҮүҺһІі"
    return bool(re.search(rf"(?<![{alphabet}]){re.escape(word.casefold())}(?![{alphabet}])", text.casefold()))


def _eligible(task: dict, content_type: str, text: str | None, is_reply_to_task: bool) -> bool:
    task_type = task["type"]
    if task_type == "daily_word":
        return content_type == "text" and bool(text) and _contains_word(text or "", task.get("word", ""))
    if task_type == "daily_question":
        return is_reply_to_task and content_type == "text" and bool((text or "").strip())
    if task_type == "photo_challenge":
        return is_reply_to_task and content_type == "photo"
    if task_type == "video_challenge":
        return is_reply_to_task and content_type in {"video", "video_note"}
    return False


async def process_daily_task_message(
    db_path: str | Path,
    task: dict,
    user: dict,
    *,
    chat_id: int,
    topic_id: int | None,
    message_id: int,
    content_type: str,
    text: str | None,
    reply_to_message_id: int | None,
) -> AwardResult:
    if task["type"] == "social_task" or int(task.get("reward", 0)) <= 0:
        return AwardResult(False, 0, reason="manual_only")
    async with connect(db_path) as db:
        await db.execute("BEGIN IMMEDIATE")
        is_reply = False
        if reply_to_message_id is not None:
            post = await (await db.execute(
                """SELECT 1 FROM daily_task_posts WHERE task_id=? AND task_date=? AND chat_id=? AND topic_id=? AND telegram_message_id=?""",
                (task["id"], task["date"], chat_id, normalize_topic_id(topic_id), reply_to_message_id),
            )).fetchone()
            is_reply = bool(post)
        if not _eligible(task, content_type, text, is_reply):
            await db.rollback()
            return AwardResult(False, 0, reason="ineligible")
        unique_key = f"daily-task:{task['date']}:{task['id']}:{user['id']}"
        result = await award_in_transaction(
            db, user["id"], int(task["reward"]), "daily_task", f"Daily task: {task['id']}", unique_key,
            username=user.get("username"), first_name=user.get("first_name", ""), chat_id=chat_id,
            topic_id=normalize_topic_id(topic_id), source_message_id=message_id, metadata={"task_id": task["id"], "task_type": task["type"]},
        )
        if not result.awarded:
            await db.rollback()
            return result
        try:
            await db.execute(
                "INSERT INTO daily_task_completions(telegram_user_id,task_id,task_date,transaction_id) VALUES(?,?,?,?)",
                (user["id"], task["id"], task["date"], result.transaction_id),
            )
        except Exception:
            await db.rollback()
            return AwardResult(False, result.new_balance - int(task["reward"]), reason="duplicate")
        await db.commit()
        return result
