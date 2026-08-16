import pytest

from app.database import connect
from app.services.activity import ActivityInput, passive_points, process_activity


def item(settings, **kwargs):
    values = dict(user_id=1, chat_id=settings.flood_chat_id, topic_id=settings.flood_topic_id, message_id=1, text="Сәлем әлем", content_type="text")
    values.update(kwargs)
    return ActivityInput(**values)


@pytest.mark.parametrize(("overrides", "expected"), [
    ({}, 1),
    ({"content_type": "photo", "text": None}, 3),
    ({"content_type": "video", "text": None}, 5),
    ({"content_type": "voice", "text": None}, 5),
    ({"content_type": "video_note", "text": None}, 5),
    ({"content_type": "sticker", "text": None}, 0),
    ({"text": "/top"}, 0),
    ({"chat_id": -999}, 0),
    ({"topic_id": 99}, 0),
])
def test_point_matrix(settings, overrides, expected):
    assert passive_points(item(settings, **overrides), settings) == expected


@pytest.mark.asyncio
async def test_message_id_and_duplicate_text(db, settings):
    first = await process_activity(db, item(settings), settings)
    duplicate_id = await process_activity(db, item(settings), settings)
    duplicate_text = await process_activity(db, item(settings, message_id=2), settings)
    assert first.awarded
    assert duplicate_id.reason == "duplicate_message"
    assert duplicate_text.reason == "duplicate_text"
    async with connect(db) as conn:
        points = (await (await conn.execute("SELECT ozgecoins FROM users WHERE user_id=1")).fetchone())[0]
    assert points == 1


@pytest.mark.asyncio
async def test_passive_daily_limit(db, settings):
    object.__setattr__(settings, "passive_daily_limit", 2)
    for n in range(3):
        result = await process_activity(db, item(settings, message_id=n + 1, text=f"Хабар {n}"), settings)
    assert result.reason == "daily_limit"
    async with connect(db) as conn:
        points = (await (await conn.execute("SELECT ozgecoins FROM users WHERE user_id=1")).fetchone())[0]
    assert points == 2


@pytest.mark.asyncio
async def test_processed_message_is_persisted(db, settings):
    await process_activity(db, item(settings, message_id=321), settings)
    async with connect(db) as conn:
        row = await (await conn.execute("SELECT user_id FROM processed_messages WHERE chat_id=? AND message_id=321", (settings.flood_chat_id,))).fetchone()
    assert row[0] == 1
