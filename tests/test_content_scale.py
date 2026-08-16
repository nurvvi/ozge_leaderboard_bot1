import json

import pytest

from app.content_import import import_content
from app.database import connect
from app.migrations import migrate


def sourced(item_id: str) -> dict:
    return {
        "id": item_id, "kk": "Сұрақ", "ru": "Вопрос", "answer": "A", "accepted_answers": ["A"],
        "options_kk": ["A", "B"], "options_ru": ["A", "B"], "correct_index": 0,
        "explanation_ru": "Проверено", "source_title": "Official source",
        "source_url": "https://example.gov.kz/source", "publisher": "Official publisher",
        "retrieved_at": "2026-08-08", "verified": True, "active": True,
    }


@pytest.mark.asyncio
async def test_json_import_supports_required_content_scale(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "proverbs.json").write_text(json.dumps([sourced(f"p-{i}") for i in range(500)]), encoding="utf-8")
    (data_dir / "facts.json").write_text(json.dumps([sourced(f"f-{i}") for i in range(1000)]), encoding="utf-8")
    (data_dir / "quiz_questions.json").write_text(json.dumps([sourced(f"q-{i}") for i in range(500)]), encoding="utf-8")
    (data_dir / "daily_tasks.json").write_text(json.dumps([{"id": "d-1", "type": "social_task", "kk": "KK", "ru": "RU", "reward": 0, "active": True}]), encoding="utf-8")
    db_path = tmp_path / "scale.db"
    await migrate(db_path)
    result = await import_content(db_path, data_dir)
    async with connect(db_path) as db:
        count = (await (await db.execute("SELECT COUNT(*) FROM game_questions WHERE verified=1 AND active=1")).fetchone())[0]
    assert result["questions"] == 2500
    assert count == 2500
