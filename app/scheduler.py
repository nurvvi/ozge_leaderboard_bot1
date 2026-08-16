from __future__ import annotations

import json
import logging
from html import escape

from aiogram import Bot
from aiogram.enums import ParseMode
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.config import Settings, telegram_thread_id
from app.database import connect
from app.services.daily_tasks import format_daily_task, get_daily_task, register_daily_task_post
from app.services.games import close_expired_games

log = logging.getLogger(__name__)


async def publish_daily(bot: Bot, settings: Settings) -> None:
    task = get_daily_task(settings.timezone)
    topic_id = settings.flood_topic_id or 0
    async with connect(settings.db_path) as db:
        await db.execute("INSERT OR IGNORE INTO scheduled_publications(publication_type,publication_date,chat_id,topic_id) VALUES('daily_task',?,?,?)", (task["date"], settings.flood_chat_id, topic_id))
        row = await (await db.execute("SELECT id,telegram_message_id FROM scheduled_publications WHERE publication_type='daily_task' AND publication_date=? AND chat_id=? AND topic_id=?", (task["date"], settings.flood_chat_id, topic_id))).fetchone()
        await db.commit()
    if row["telegram_message_id"]:
        return
    try:
        sent = await bot.send_message(settings.flood_chat_id, format_daily_task(task), message_thread_id=telegram_thread_id(settings.flood_topic_id), parse_mode=ParseMode.HTML)
        await register_daily_task_post(settings.db_path, task, settings.flood_chat_id, settings.flood_topic_id, sent.message_id)
        async with connect(settings.db_path) as db:
            await db.execute("UPDATE scheduled_publications SET telegram_message_id=?,status='published' WHERE id=?", (sent.message_id, row["id"])); await db.commit()
    except Exception:
        log.exception("Daily publication failed")


async def finish_games(bot: Bot, settings: Settings) -> None:
    for game in await close_expired_games(settings.db_path):
        kk = json.loads(game["options_kk_json"])
        ru = json.loads(game["options_ru_json"])
        text = (f"🎮 <b>Уақыт аяқталды</b>\nДұрыс жауап: {escape(kk[game['correct_index']])}\n\n<b>Время вышло</b>\nПравильный ответ: {escape(ru[game['correct_index']])}")
        try:
            await bot.send_message(game["chat_id"], text, message_thread_id=telegram_thread_id(game["topic_id"]), parse_mode=ParseMode.HTML)
        except Exception:
            log.exception("Could not publish game result for session %s", game["id"])


def build_scheduler(bot: Bot, settings: Settings) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=settings.timezone)
    if settings.daily_post_enabled:
        scheduler.add_job(publish_daily, CronTrigger(hour=settings.daily_post_hour, minute=settings.daily_post_minute, timezone=settings.timezone), args=(bot, settings), id="daily-post", replace_existing=True, max_instances=1, coalesce=True)
    scheduler.add_job(finish_games, "interval", seconds=30, args=(bot, settings), id="finish-games", replace_existing=True, max_instances=1, coalesce=True)
    return scheduler
