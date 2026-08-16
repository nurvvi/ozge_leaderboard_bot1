import pytest

from app.content_import import import_content
from app.database import connect
from app.services.rewards import award_ozgecoins


@pytest.mark.asyncio
async def test_reward_ledger_matches_balance(db):
    await award_ozgecoins(db, 10, 8, "game", "win", unique_key="win:10")
    await award_ozgecoins(db, 10, -3, "admin_adjustment", "correction", unique_key="fix:10", admin_id=99)
    async with connect(db) as conn:
        points = (await (await conn.execute("SELECT ozgecoins FROM users WHERE user_id=10")).fetchone())[0]
        ledger = (await (await conn.execute("SELECT SUM(amount) FROM ozgecoin_transactions WHERE telegram_user_id=10")).fetchone())[0]
    assert points == ledger == 5


@pytest.mark.asyncio
async def test_content_import_is_idempotent(db):
    await import_content(db)
    async with connect(db) as conn:
        row = await (await conn.execute("SELECT COUNT(*),(SELECT COUNT(*) FROM game_questions WHERE verified=1 AND active=1) FROM game_questions")).fetchone()
    assert tuple(row) == (17, 17)


@pytest.mark.asyncio
async def test_deduction_cannot_make_negative_balance(db):
    await award_ozgecoins(db, 11, 4, "game", "win", unique_key="win:11")
    result = await award_ozgecoins(db, 11, -99, "admin_adjustment", "correction", unique_key="fix:11", admin_id=99)
    async with connect(db) as conn:
        event = await (await conn.execute("SELECT amount FROM ozgecoin_transactions WHERE unique_key='fix:11'")).fetchone()
    assert result.new_balance == 0 and event[0] == -4


@pytest.mark.asyncio
async def test_rewards_do_not_update_legacy_achievement_tables(db):
    result = await award_ozgecoins(
        db,
        12,
        3,
        "daily_task",
        "daily reward",
        unique_key="daily:12",
        counter_updates={"legacy_counter": 1},
    )
    async with connect(db) as conn:
        counts = await (await conn.execute(
            "SELECT (SELECT COUNT(*) FROM user_counters),(SELECT COUNT(*) FROM user_achievements)"
        )).fetchone()
    assert result.new_balance == 3
    assert tuple(counts) == (0, 0)
