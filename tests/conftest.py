from pathlib import Path

import pytest

from app.config import Settings
from app.content_import import import_content
from app.migrations import migrate


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return Settings(
        bot_token="test", flood_chat_id=-1001, flood_topic_id=5, admin_ids=frozenset({99}),
        db_path=tmp_path / "test.db", legacy_db_path=None, timezone="Asia/Almaty",
        daily_post_enabled=False, daily_post_hour=10, daily_post_minute=0, daily_content_type="rotate",
        game_duration_minutes=60, text_points=1, photo_points=3, video_points=5, voice_points=5, video_note_points=5,
        word_of_day_points=3, default_game_points=5, quote_points=5, passive_daily_limit=100,
        message_cooldown_seconds=10, min_meaningful_text_length=3,
    )


@pytest.fixture
async def db(settings: Settings):
    await migrate(settings.db_path)
    await import_content(settings.db_path)
    return settings.db_path
