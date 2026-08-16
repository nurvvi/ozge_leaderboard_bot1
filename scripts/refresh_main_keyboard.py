from __future__ import annotations

import asyncio
import os

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramMigrateToChat

from app.database import connect
from app.keyboards import main_keyboard


async def send_keyboard(bot: Bot, chat_id: int, thread_id: int | None = None) -> int | None:
    try:
        await bot.send_message(
            chat_id,
            "Мәзір жаңартылды.\n\nМеню обновлено.",
            message_thread_id=thread_id or None,
            reply_markup=main_keyboard(),
        )
        return chat_id
    except TelegramForbiddenError:
        return None
    except TelegramMigrateToChat as exc:
        await bot.send_message(
            exc.migrate_to_chat_id,
            "Мәзір жаңартылды.\n\nМеню обновлено.",
            message_thread_id=thread_id or None,
            reply_markup=main_keyboard(),
        )
        return exc.migrate_to_chat_id


async def main() -> None:
    token = os.environ.get("BOT_TOKEN", "").strip()
    if not token:
        raise SystemExit("BOT_TOKEN is required")
    flood_chat_id = int(os.environ["FLOOD_CHAT_ID"])
    flood_topic_id = int(os.environ.get("FLOOD_TOPIC_ID", "0"))
    db_path = os.environ.get("DB_PATH", "activity_bot.db")
    async with connect(db_path) as db:
        user_ids = [row[0] for row in await (await db.execute("SELECT telegram_id FROM users WHERE telegram_id IS NOT NULL")).fetchall()]
    bot = Bot(token)
    refreshed: list[int] = []
    try:
        for chat_id in dict.fromkeys([flood_chat_id, *user_ids]):
            thread_id = flood_topic_id if chat_id == flood_chat_id else None
            refreshed_chat = await send_keyboard(bot, chat_id, thread_id)
            if refreshed_chat is not None:
                refreshed.append(refreshed_chat)
    finally:
        await bot.session.close()
    print(f"refreshed chats: {len(refreshed)}")


if __name__ == "__main__":
    asyncio.run(main())
