from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware, Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import TelegramObject

from app.bot_commands import sync_bot_commands
from app.config import Settings
from app.content_import import import_content
from app.handlers import activity, admin, common, daily, games
from app.middleware.flood_scope import FloodScopeMiddleware
from app.migrations import migrate
from app.scheduler import build_scheduler

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
log = logging.getLogger("qazaq_identity_bot")


class AppMiddleware(BaseMiddleware):
    def __init__(self, settings: Settings):
        self.settings = settings

    async def __call__(self, handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]], event: TelegramObject, data: dict[str, Any]) -> Any:
        data["settings"] = self.settings
        data["db_path"] = str(self.settings.db_path)
        return await handler(event, data)


async def main() -> None:
    settings = Settings.from_env()
    await migrate(settings.db_path, settings.legacy_db_path)
    await import_content(settings.db_path)
    bot = Bot(settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher()
    dp.update.outer_middleware(AppMiddleware(settings))
    flood_scope = FloodScopeMiddleware()
    dp.message.middleware(flood_scope)
    dp.callback_query.middleware(flood_scope)
    dp.include_routers(admin.router, common.router, daily.router, games.router, activity.router)
    flood_chat_id = await sync_bot_commands(bot, settings.flood_chat_id)
    log.info(
        "Flood scope: chat_id=%s topic_id=%s",
        flood_chat_id,
        settings.flood_topic_id or "main (0)",
    )
    scheduler = build_scheduler(bot, settings)
    scheduler.start()
    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
    except Exception:
        log.exception("Fatal startup error")
        raise
