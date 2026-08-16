from __future__ import annotations

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message

from app.config import Settings
from app.services.daily_tasks import format_daily_task, get_daily_task, register_daily_task_post

router = Router()


@router.message(Command("daily"))
@router.message(F.text == "📅 Күн тапсырмасы / Задание дня")
async def daily(message: Message, db_path: str, settings: Settings) -> None:
    task = get_daily_task(settings.timezone)
    sent = await message.answer(format_daily_task(task), parse_mode=ParseMode.HTML)
    await register_daily_task_post(db_path, task, message.chat.id, message.message_thread_id, sent.message_id)
