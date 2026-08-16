from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.config import in_flood_scope
from app.handlers.common import profile
from app.services.daily_tasks import get_daily_task
from app.services.games import answer_game, start_game
from app.services.users import get_profile, upsert_user


@pytest.mark.asyncio
async def test_two_telegram_ids_have_separate_profiles(db):
    await upsert_user(db, 1028702642, "yeonienonie", "Owner")
    old = await get_profile(db, 1129763368)
    new = await get_profile(db, 1028702642)
    assert old is None
    assert new["telegram_id"] == 1028702642 and new["ozgecoins"] == 0


@pytest.mark.asyncio
async def test_new_owner_id_does_not_receive_legacy_points(tmp_path):
    from app.migrations import migrate
    import sqlite3
    path = tmp_path / "legacy.db"
    raw = sqlite3.connect(path)
    raw.execute("CREATE TABLE users(user_id INTEGER PRIMARY KEY,username TEXT,first_name TEXT,points INTEGER DEFAULT 0)")
    raw.execute("INSERT INTO users VALUES(1129763368,'Raamchik','Ramchik',16)"); raw.commit(); raw.close()
    await migrate(path)
    await upsert_user(path, 1028702642, "yeonienonie", "Owner")
    assert (await get_profile(path, 1129763368))["ozgecoins"] == 0
    assert (await get_profile(path, 1028702642))["ozgecoins"] == 0


@pytest.mark.asyncio
async def test_my_rating_uses_message_sender(db):
    sender = SimpleNamespace(id=202, username="sender", first_name="Sender")
    message = SimpleNamespace(from_user=sender, answer=AsyncMock())
    await profile(message, str(db))
    sent_text = message.answer.await_args.args[0]
    assert "@sender" in sent_text
    assert "ÖZGEcoins" in sent_text
    assert "activity_points" not in sent_text and " AP" not in sent_text and "game coins" not in sent_text
    assert (await get_profile(db, 202))["telegram_id"] == 202


def test_flood_topic_zero_matches_main_chat(settings):
    object.__setattr__(settings, "flood_topic_id", 0)
    assert in_flood_scope(settings.flood_chat_id, None, settings)
    assert in_flood_scope(settings.flood_chat_id, 0, settings)
    assert not in_flood_scope(settings.flood_chat_id, 5, settings)


def test_flood_topic_filters_specific_topic(settings):
    object.__setattr__(settings, "flood_topic_id", 5)
    assert in_flood_scope(settings.flood_chat_id, 5, settings)
    assert not in_flood_scope(settings.flood_chat_id, None, settings)


def test_daily_task_is_stable_in_almaty_day():
    first = get_daily_task("Asia/Almaty", datetime(2026, 8, 3, 19, 1, tzinfo=timezone.utc))
    second = get_daily_task("Asia/Almaty", datetime(2026, 8, 4, 17, 59, tzinfo=timezone.utc))
    assert first["date"] == second["date"] == "2026-08-04"
    assert first["id"] == second["id"]


@pytest.mark.asyncio
async def test_regular_member_starts_and_wins_three_coins_once(db):
    game = await start_game(db, "proverb_finish", -1001, 5, 60, created_by=555)
    user = {"id": 555, "username": "member", "first_name": "Member"}
    winner, _ = await answer_game(db, game["session_id"], user, game["correct_index"])
    repeated, _ = await answer_game(db, game["session_id"], user, game["correct_index"])
    assert winner.won and winner.ozgecoins == 3
    assert repeated.reason == "closed"
    assert (await get_profile(db, 555))["ozgecoins"] == 3
