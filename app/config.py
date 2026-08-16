from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _int(name: str, default: int | None = None) -> int:
    value = os.getenv(name)
    if value in (None, ""):
        if default is None:
            raise ValueError(f"{name} must be set to an integer")
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    if value.lower() in {"1", "true", "yes", "on"}:
        return True
    if value.lower() in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be true or false")


def _admin_ids() -> frozenset[int]:
    raw = os.getenv("ADMIN_IDS", "")
    try:
        return frozenset(int(item.strip()) for item in raw.split(",") if item.strip())
    except ValueError as exc:
        raise ValueError("ADMIN_IDS must be a comma-separated list of integers") from exc


@dataclass(frozen=True)
class Settings:
    bot_token: str
    flood_chat_id: int
    flood_topic_id: int
    admin_ids: frozenset[int]
    db_path: Path
    legacy_db_path: Path | None
    timezone: str
    daily_post_enabled: bool
    daily_post_hour: int
    daily_post_minute: int
    daily_content_type: str
    game_duration_minutes: int
    text_points: int
    photo_points: int
    video_points: int
    voice_points: int
    video_note_points: int
    word_of_day_points: int
    default_game_points: int
    quote_points: int
    passive_daily_limit: int
    message_cooldown_seconds: int
    min_meaningful_text_length: int

    @classmethod
    def from_env(cls) -> "Settings":
        token = os.getenv("BOT_TOKEN", "").strip()
        if not token:
            raise ValueError("BOT_TOKEN is required")
        db_path = Path(os.getenv("DB_PATH", "activity_bot.db")).expanduser()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        legacy_raw = os.getenv("LEGACY_DB_PATH", "flood_stats.db").strip()
        settings = cls(
            bot_token=token,
            flood_chat_id=_int("FLOOD_CHAT_ID"),
            flood_topic_id=_int("FLOOD_TOPIC_ID"),
            admin_ids=_admin_ids(),
            db_path=db_path,
            legacy_db_path=Path(legacy_raw).expanduser() if legacy_raw else None,
            timezone=os.getenv("TIMEZONE", "Asia/Almaty"),
            daily_post_enabled=_bool("DAILY_POST_ENABLED", True),
            daily_post_hour=_int("DAILY_POST_HOUR", 10),
            daily_post_minute=_int("DAILY_POST_MINUTE", 0),
            daily_content_type=os.getenv("DAILY_CONTENT_TYPE", "rotate"),
            game_duration_minutes=_int("GAME_DURATION_MINUTES", 60),
            text_points=_int("TEXT_POINTS", 1),
            photo_points=_int("PHOTO_POINTS", 3),
            video_points=_int("VIDEO_POINTS", 5),
            voice_points=_int("VOICE_POINTS", 5),
            video_note_points=_int("VIDEO_NOTE_POINTS", 5),
            word_of_day_points=_int("WORD_OF_DAY_POINTS", 3),
            default_game_points=_int("DEFAULT_GAME_POINTS", 5),
            quote_points=_int("QUOTE_POINTS", 5),
            passive_daily_limit=_int("PASSIVE_DAILY_LIMIT", 100),
            message_cooldown_seconds=_int("MESSAGE_COOLDOWN_SECONDS", 10),
            min_meaningful_text_length=_int("MIN_MEANINGFUL_TEXT_LENGTH", 3),
        )
        if not 0 <= settings.daily_post_hour <= 23 or not 0 <= settings.daily_post_minute <= 59:
            raise ValueError("DAILY_POST_HOUR/MINUTE contain an invalid time")
        if settings.game_duration_minutes < 1 or settings.passive_daily_limit < 0:
            raise ValueError("GAME_DURATION_MINUTES must be positive and PASSIVE_DAILY_LIMIT non-negative")
        return settings


def normalize_topic_id(topic_id: int | None) -> int:
    """Telegram uses None for the main chat; persist and compare it as topic 0."""
    return int(topic_id or 0)


def in_flood_scope(chat_id: int, topic_id: int | None, settings: Settings) -> bool:
    return chat_id == settings.flood_chat_id and normalize_topic_id(topic_id) == normalize_topic_id(settings.flood_topic_id)


def telegram_thread_id(topic_id: int | None) -> int | None:
    normalized = normalize_topic_id(topic_id)
    return normalized or None
