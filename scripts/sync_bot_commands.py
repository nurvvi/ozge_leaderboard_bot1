from __future__ import annotations

import asyncio
import os

from aiogram import Bot

from app.bot_commands import BOT_COMMANDS, LANGUAGE_CODES, command_scopes, sync_bot_commands


BLOCKED_COMMANDS = {"achievements", "achievement", "badges", "badge"}
BLOCKED_LABELS = ("Жетістіктер", "Достижения")


async def main() -> None:
    token = os.environ.get("BOT_TOKEN", "").strip()
    if not token:
        raise SystemExit("BOT_TOKEN is required")
    try:
        chat_id = int(os.environ["FLOOD_CHAT_ID"])
    except (KeyError, ValueError):
        raise SystemExit("FLOOD_CHAT_ID is required and must be an integer") from None
    bot = Bot(token)
    try:
        chat_id = await sync_bot_commands(bot, chat_id)
        menus = []
        for scope in command_scopes(chat_id):
            for language_code in LANGUAGE_CODES:
                commands = await bot.get_my_commands(scope=scope, language_code=language_code)
                menus.append((scope.type, language_code or "default", commands))
        expected = [item.command for item in BOT_COMMANDS]
        default_commands = await bot.get_my_commands()
        if [item.command for item in default_commands] != expected:
            raise RuntimeError("Telegram default command menu does not match the configured list")
        for scope, language, commands in menus:
            names = [item.command for item in commands]
            if BLOCKED_COMMANDS.intersection(names):
                raise RuntimeError(f"Blocked command remains in {scope}/{language} menu")
            if any(label in item.description for item in commands for label in BLOCKED_LABELS):
                raise RuntimeError(f"Blocked label remains in {scope}/{language} menu")
        print(f"final: {', '.join('/' + name for name in expected)}")
        print(f"verified scopes: {len(menus)}")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
