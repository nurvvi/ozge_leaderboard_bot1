from datetime import datetime, timedelta, timezone

import pytest

from app.database import connect
from app.services.games import answer_game, start_game
from app.services.users import render_top
from app.handlers.games import format_game_result


@pytest.mark.asyncio
@pytest.mark.parametrize("game_type", ["proverb_finish", "true_false", "interesting_fact"])
async def test_each_supported_game_starts_and_can_be_completed(db, game_type):
    game = await start_game(db, game_type, -1001, 5, 60, 12345)
    result, _ = await answer_game(
        db,
        game["session_id"],
        {"id": 700, "username": "player", "first_name": "Player"},
        game["correct_index"],
    )
    assert result.won
    assert result.ozgecoins == 3


@pytest.mark.asyncio
async def test_game_answers_and_repeat(db):
    game = await start_game(db, "true_false", -1001, 5, 60, 12345)
    correct = game["correct_index"]
    wrong = 1 - correct
    good, _ = await answer_game(db, game["session_id"], {"id": 1, "first_name": "A"}, correct)
    repeat, _ = await answer_game(db, game["session_id"], {"id": 1, "first_name": "A"}, correct)
    bad, _ = await answer_game(db, game["session_id"], {"id": 2, "first_name": "B"}, wrong)
    assert good.won and good.ozgecoins == 3 and repeat.reason == "closed" and bad.reason == "closed"


@pytest.mark.asyncio
async def test_only_one_group_game_and_state_persists(db):
    game = await start_game(db, "proverb_finish", -1001, 5, 60, 12345)
    with pytest.raises(ValueError):
        await start_game(db, "interesting_fact", -1001, 5, 60, 12345)
    async with connect(db) as conn:
        row = await (await conn.execute("SELECT status,question_id,ends_at FROM game_sessions WHERE id=?", (game["session_id"],))).fetchone()
    assert row["status"] == "active" and row["question_id"]


def test_html_is_escaped():
    text = render_top([{"user_id": 1, "username": None, "first_name": "<b>evil</b>", "ozgecoins": 3}])
    assert "&lt;b&gt;evil&lt;/b&gt;" in text and "<b>evil</b>" not in text
    assert "ÖZGEcoins" in text and "activity_points" not in text and " AP" not in text


def test_game_result_never_shows_source_url():
    game = {"options_kk_json": '["Дұрыс"]', "options_ru_json": '["Верно"]', "correct_index": 0, "source_url": "https://secret.example/source"}
    text = format_game_result(game, "@winner")
    assert "https://" not in text and "source" not in text.casefold()
    assert "@winner" in text and "+3 ÖZGEcoins" in text
