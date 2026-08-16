import pytest

from app.database import connect
from app.services.daily_tasks import process_daily_task_message, register_daily_task_post
from app.services.rewards import award_ozgecoins


USER = {"id": 77, "username": "daily_user", "first_name": "Daily"}


def task(task_type: str, reward: int, **extra):
    return {"id": f"test-{task_type}", "type": task_type, "kk": "KK", "ru": "RU", "reward": reward, "active": True, "date": "2026-08-08", **extra}


async def complete(db, current_task, *, kind="text", text="Жауап", reply_id=None, message_id=10):
    return await process_daily_task_message(
        db, current_task, USER, chat_id=-1001, topic_id=5, message_id=message_id,
        content_type=kind, text=text, reply_to_message_id=reply_id,
    )


@pytest.mark.asyncio
async def test_daily_word_rewards_only_once(db):
    current = task("daily_word", 3, word="кітап")
    first = await complete(db, current, text="Мен КІТАП оқыдым", message_id=1)
    second = await complete(db, current, text="Бұл кітап жақсы", message_id=2)
    assert first.awarded and first.new_balance == 3
    assert second.reason == "duplicate"


@pytest.mark.asyncio
async def test_daily_question_reply_rewards_only_once(db):
    current = task("daily_question", 3)
    await register_daily_task_post(db, current, -1001, 5, 500)
    no_reply = await complete(db, current, text="Навык", message_id=3)
    first = await complete(db, current, text="Навык", reply_id=500, message_id=4)
    second = await complete(db, current, text="Другой", reply_id=500, message_id=5)
    assert no_reply.reason == "ineligible"
    assert first.awarded and first.new_balance == 3
    assert second.reason == "duplicate"


@pytest.mark.asyncio
async def test_photo_challenge(db):
    current = task("photo_challenge", 5)
    await register_daily_task_post(db, current, -1001, 5, 501)
    wrong = await complete(db, current, kind="text", reply_id=501, message_id=6)
    result = await complete(db, current, kind="photo", text=None, reply_id=501, message_id=7)
    assert wrong.reason == "ineligible"
    assert result.awarded and result.new_balance == 5


@pytest.mark.parametrize("kind", ["video", "video_note"])
@pytest.mark.asyncio
async def test_video_challenge_accepts_video_and_circle(db, kind):
    current = task("video_challenge", 5)
    current["id"] += f"-{kind}"
    await register_daily_task_post(db, current, -1001, 5, 502)
    result = await complete(db, current, kind=kind, text=None, reply_id=502, message_id=8)
    assert result.awarded and result.new_balance == 5


@pytest.mark.asyncio
async def test_social_task_has_no_automatic_reward(db):
    current = task("social_task", 0)
    result = await complete(db, current, text="Выполнено", message_id=9)
    assert not result.awarded and result.reason == "manual_only"
    async with connect(db) as conn:
        count = (await (await conn.execute("SELECT COUNT(*) FROM ozgecoin_transactions WHERE telegram_user_id=?", (USER["id"],))).fetchone())[0]
    assert count == 0


@pytest.mark.asyncio
async def test_admin_id_is_recorded(db):
    await award_ozgecoins(db, 4, 9, "admin_adjustment", "manual", admin_id=99, unique_key="admin:1")
    async with connect(db) as conn:
        row = await (await conn.execute("SELECT admin_id FROM ozgecoin_transactions WHERE unique_key='admin:1'")).fetchone()
    assert row[0] == 99
