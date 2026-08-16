from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.enums import ChatType
from aiogram.types import CallbackQuery, Message, TelegramObject

from app.config import Settings, in_flood_scope


class FloodScopeMiddleware(BaseMiddleware):
    """Process only messages and callbacks inside the configured FLOOD topic."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        settings: Settings = data["settings"]

        if isinstance(event, Message):
            if event.chat.type == ChatType.PRIVATE:
                if event.from_user and event.from_user.id in settings.admin_ids:
                    return await handler(event, data)
                return None
            # Allow administrators to discover a chat/topic ID before adding it
            # to the restricted flood scope.
            if (
                event.from_user
                and event.from_user.id in settings.admin_ids
                and (event.text or "").split("@", 1)[0] == "/where"
            ):
                return await handler(event, data)
            if not in_flood_scope(event.chat.id, event.message_thread_id, settings):
                return None

        elif isinstance(event, CallbackQuery):
            message = event.message
            if not message or not in_flood_scope(message.chat.id, message.message_thread_id, settings):
                if event.id:
                    await event.answer()
                return None

        return await handler(event, data)
