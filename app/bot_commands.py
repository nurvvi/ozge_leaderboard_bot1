from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramMigrateToChat
from aiogram.types import (
    BotCommand,
    BotCommandScope,
    BotCommandScopeAllChatAdministrators,
    BotCommandScopeAllGroupChats,
    BotCommandScopeAllPrivateChats,
    BotCommandScopeChat,
    BotCommandScopeChatAdministrators,
    BotCommandScopeDefault,
)

log = logging.getLogger(__name__)


BOT_COMMANDS = [
    BotCommand(command="start", description="Бастау / Начать"),
    BotCommand(command="help", description="Ережелер / Правила"),
    BotCommand(command="profile", description="Менің рейтингім / Мой рейтинг"),
    BotCommand(command="top", description="Көшбасшылар / Лидерборд"),
    BotCommand(command="daily", description="Күн тапсырмасы / Задание дня"),
    BotCommand(command="games", description="Ойындар / Игры"),
    BotCommand(command="admin", description="Әкімші / Admin"),
    BotCommand(command="where", description="Chat және topic ID / ID чата и темы"),
]

LANGUAGE_CODES: tuple[str | None, ...] = (None, "ru", "kk")


def command_scopes(chat_id: int) -> tuple[BotCommandScope, ...]:
    return (
        BotCommandScopeDefault(),
        BotCommandScopeAllPrivateChats(),
        BotCommandScopeAllGroupChats(),
        BotCommandScopeAllChatAdministrators(),
        BotCommandScopeChat(chat_id=chat_id),
        BotCommandScopeChatAdministrators(chat_id=chat_id),
    )


async def resolve_command_chat_id(bot: Bot, chat_id: int) -> int:
    try:
        await bot.get_chat(chat_id)
    except TelegramMigrateToChat as exc:
        log.info("Command scope chat migrated from %s to %s", chat_id, exc.migrate_to_chat_id)
        return exc.migrate_to_chat_id
    return chat_id


async def sync_bot_commands(bot: Bot, chat_id: int) -> int:
    """Clear every relevant command override, then register the current default menu."""
    chat_id = await resolve_command_chat_id(bot, chat_id)
    for attempt in range(2):
        targets = [
            (scope, language_code)
            for scope in command_scopes(chat_id)
            for language_code in LANGUAGE_CODES
        ]
        try:
            await asyncio.gather(*(
                bot.delete_my_commands(scope=scope, language_code=language_code)
                for scope, language_code in targets
            ))
            break
        except TelegramMigrateToChat as exc:
            if attempt:
                raise
            log.info("Command scope chat migrated from %s to %s", chat_id, exc.migrate_to_chat_id)
            chat_id = exc.migrate_to_chat_id
    await bot.set_my_commands(BOT_COMMANDS, scope=BotCommandScopeChat(chat_id=chat_id))
    log.info("Bot commands registered for chat %s only", chat_id)
    return chat_id
