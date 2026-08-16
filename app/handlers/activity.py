from __future__ import annotations

import logging

from aiogram import Router
from aiogram.types import Message

from app.config import Settings
from app.services.activity import ActivityInput, process_activity
from app.services.daily_tasks import get_daily_task, process_daily_task_message
from app.services.users import upsert_user

router = Router()
log = logging.getLogger(__name__)


def content_type(message: Message) -> str:
    if message.photo: return "photo"
    if message.video: return "video"
    if message.voice: return "voice"
    if message.video_note: return "video_note"
    if message.sticker: return "sticker"
    if message.text: return "text"
    if message.document: return "document"
    if message.animation: return "animation"
    if message.audio: return "audio"
    return "service"


@router.message()
async def all_messages(message: Message, db_path: str, settings: Settings) -> None:
    user = message.from_user
    if not user or user.is_bot:
        return
    await upsert_user(db_path, user.id, user.username, user.first_name)
    kind = content_type(message)
    activity = await process_activity(
        db_path,
        ActivityInput(
            user_id=user.id, chat_id=message.chat.id, topic_id=message.message_thread_id,
            message_id=message.message_id, username=user.username, first_name=user.first_name,
            text=message.text or message.caption, content_type=kind, is_bot=user.is_bot,
            is_forwarded=bool(message.forward_origin), is_service=kind == "service",
        ),
        settings,
    )
    if activity.reason and activity.reason.startswith("duplicate"):
        log.info("Repeat ignored user=%s chat=%s message=%s reason=%s", user.id, message.chat.id, message.message_id, activity.reason)
    task = get_daily_task(settings.timezone)
    daily = await process_daily_task_message(
        db_path, task, {"id": user.id, "username": user.username, "first_name": user.first_name},
        chat_id=message.chat.id, topic_id=message.message_thread_id, message_id=message.message_id,
        content_type=kind, text=message.text or message.caption,
        reply_to_message_id=message.reply_to_message.message_id if message.reply_to_message else None,
    )
    if daily.awarded:
        await message.reply(f"+{task['reward']} ÖZGEcoins")
