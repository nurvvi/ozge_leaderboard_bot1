from aiogram.enums import ChatType
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.middleware.flood_scope import FloodScopeMiddleware


@pytest.fixture
def middleware(settings):
    return FloodScopeMiddleware()


def _data(settings):
    return {"settings": settings}


@pytest.mark.asyncio
async def test_middleware_allows_flood_topic_message(middleware, settings):
    handler = AsyncMock(return_value="ok")
    message = SimpleNamespace(
        chat=SimpleNamespace(type=ChatType.SUPERGROUP, id=settings.flood_chat_id),
        message_thread_id=settings.flood_topic_id,
        from_user=SimpleNamespace(id=1),
    )
    result = await middleware(handler, message, _data(settings))
    assert result == "ok"
    handler.assert_awaited_once()


@pytest.mark.asyncio
async def test_middleware_blocks_other_topic_silently(middleware, settings):
    handler = AsyncMock()
    message = SimpleNamespace(
        chat=SimpleNamespace(type=ChatType.SUPERGROUP, id=settings.flood_chat_id),
        message_thread_id=99,
        from_user=SimpleNamespace(id=1),
    )
    result = await middleware(handler, message, _data(settings))
    assert result is None
    handler.assert_not_awaited()


@pytest.mark.asyncio
async def test_middleware_blocks_other_chat_silently(middleware, settings):
    handler = AsyncMock()
    message = SimpleNamespace(
        chat=SimpleNamespace(type=ChatType.SUPERGROUP, id=-9999),
        message_thread_id=settings.flood_topic_id,
        from_user=SimpleNamespace(id=1),
    )
    result = await middleware(handler, message, _data(settings))
    assert result is None
    handler.assert_not_awaited()


@pytest.mark.asyncio
async def test_middleware_blocks_private_chat_for_regular_user(middleware, settings):
    handler = AsyncMock()
    message = SimpleNamespace(
        chat=SimpleNamespace(type=ChatType.PRIVATE, id=1),
        message_thread_id=None,
        from_user=SimpleNamespace(id=123),
    )
    result = await middleware(handler, message, _data(settings))
    assert result is None
    handler.assert_not_awaited()


@pytest.mark.asyncio
async def test_middleware_allows_private_chat_for_admin(middleware, settings):
    handler = AsyncMock(return_value="admin")
    message = SimpleNamespace(
        chat=SimpleNamespace(type=ChatType.PRIVATE, id=1),
        message_thread_id=None,
        from_user=SimpleNamespace(id=99),
    )
    result = await middleware(handler, message, _data(settings))
    assert result == "admin"
    handler.assert_awaited_once()


@pytest.mark.asyncio
async def test_middleware_blocks_callback_outside_flood(middleware, settings):
    handler = AsyncMock()
    callback = SimpleNamespace(
        id="cb1",
        message=SimpleNamespace(chat=SimpleNamespace(id=settings.flood_chat_id), message_thread_id=77),
        answer=AsyncMock(),
    )
    result = await middleware(handler, callback, _data(settings))
    assert result is None
    handler.assert_not_awaited()
    callback.answer.assert_awaited_once()
