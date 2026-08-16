from __future__ import annotations

import json
from pathlib import Path

from app.database import connect


MIGRATIONS: list[tuple[int, str]] = [
    (1, """
    CREATE TABLE IF NOT EXISTS schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS users(user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT NOT NULL DEFAULT '', points INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, last_activity_date TEXT, active_days INTEGER NOT NULL DEFAULT 0, completed_tasks_count INTEGER NOT NULL DEFAULT 0, correct_answers_count INTEGER NOT NULL DEFAULT 0);
    CREATE TABLE IF NOT EXISTS reward_events(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, chat_id INTEGER, topic_id INTEGER, source_message_id INTEGER, event_type TEXT NOT NULL, points_delta INTEGER NOT NULL, reason TEXT NOT NULL, unique_key TEXT UNIQUE, admin_id INTEGER, metadata_json TEXT NOT NULL DEFAULT '{}', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(user_id) REFERENCES users(user_id));
    CREATE TABLE IF NOT EXISTS processed_messages(chat_id INTEGER NOT NULL, message_id INTEGER NOT NULL, user_id INTEGER NOT NULL, normalized_text TEXT, processed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(chat_id,message_id));
    CREATE TABLE IF NOT EXISTS daily_content(id INTEGER PRIMARY KEY AUTOINCREMENT, external_id TEXT NOT NULL UNIQUE, content_type TEXT NOT NULL, title TEXT NOT NULL, body TEXT NOT NULL, normalized_value TEXT, extra_json TEXT NOT NULL DEFAULT '{}', reward_points INTEGER NOT NULL DEFAULT 0, category TEXT, active INTEGER NOT NULL DEFAULT 1, rotation_order INTEGER NOT NULL DEFAULT 0);
    CREATE TABLE IF NOT EXISTS daily_posts(id INTEGER PRIMARY KEY AUTOINCREMENT, content_id INTEGER NOT NULL, chat_id INTEGER NOT NULL, topic_id INTEGER, telegram_message_id INTEGER, publication_date TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'reserved', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, cancelled_at TEXT, UNIQUE(content_id,publication_date,chat_id), FOREIGN KEY(content_id) REFERENCES daily_content(id));
    CREATE TABLE IF NOT EXISTS daily_responses(id INTEGER PRIMARY KEY AUTOINCREMENT, daily_post_id INTEGER NOT NULL, user_id INTEGER NOT NULL, source_message_id INTEGER, response_type TEXT NOT NULL, awarded INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE(daily_post_id,user_id), FOREIGN KEY(daily_post_id) REFERENCES daily_posts(id));
    CREATE TABLE IF NOT EXISTS tasks(id INTEGER PRIMARY KEY AUTOINCREMENT, external_id TEXT NOT NULL UNIQUE, title TEXT NOT NULL, text TEXT NOT NULL, expected_response_type TEXT NOT NULL, reward_points INTEGER NOT NULL, category TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1, is_team_challenge INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS task_posts(id INTEGER PRIMARY KEY AUTOINCREMENT, task_id INTEGER NOT NULL, chat_id INTEGER NOT NULL, topic_id INTEGER, telegram_message_id INTEGER, status TEXT NOT NULL DEFAULT 'active', created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(task_id) REFERENCES tasks(id));
    CREATE TABLE IF NOT EXISTS task_submissions(id INTEGER PRIMARY KEY AUTOINCREMENT, task_post_id INTEGER NOT NULL, user_id INTEGER NOT NULL, source_message_id INTEGER, response_type TEXT NOT NULL, awarded INTEGER NOT NULL DEFAULT 0, created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE(task_post_id,user_id), FOREIGN KEY(task_post_id) REFERENCES task_posts(id));
    CREATE TABLE IF NOT EXISTS game_questions(id INTEGER PRIMARY KEY AUTOINCREMENT, external_id TEXT NOT NULL UNIQUE, game_type TEXT NOT NULL, prompt TEXT NOT NULL, options_json TEXT NOT NULL, correct_index INTEGER NOT NULL, explanation TEXT NOT NULL, difficulty TEXT NOT NULL DEFAULT 'normal', reward_points INTEGER NOT NULL DEFAULT 5, active INTEGER NOT NULL DEFAULT 1);
    CREATE TABLE IF NOT EXISTS game_sessions(id INTEGER PRIMARY KEY AUTOINCREMENT, question_id INTEGER NOT NULL, chat_id INTEGER NOT NULL, topic_id INTEGER, telegram_message_id INTEGER, status TEXT NOT NULL DEFAULT 'active', starts_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, ends_at TEXT NOT NULL, created_by INTEGER, FOREIGN KEY(question_id) REFERENCES game_questions(id));
    CREATE TABLE IF NOT EXISTS game_answers(id INTEGER PRIMARY KEY AUTOINCREMENT, session_id INTEGER NOT NULL, user_id INTEGER NOT NULL, selected_index INTEGER NOT NULL, is_correct INTEGER NOT NULL, points_awarded INTEGER NOT NULL DEFAULT 0, answered_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE(session_id,user_id), FOREIGN KEY(session_id) REFERENCES game_sessions(id));
    CREATE TABLE IF NOT EXISTS achievements(id INTEGER PRIMARY KEY AUTOINCREMENT, code TEXT NOT NULL UNIQUE, title TEXT NOT NULL, description TEXT NOT NULL, counter_key TEXT NOT NULL, threshold INTEGER NOT NULL, bonus_points INTEGER NOT NULL DEFAULT 0, active INTEGER NOT NULL DEFAULT 1);
    CREATE TABLE IF NOT EXISTS user_achievements(id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, achievement_id INTEGER NOT NULL, unlocked_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, UNIQUE(user_id,achievement_id), FOREIGN KEY(user_id) REFERENCES users(user_id), FOREIGN KEY(achievement_id) REFERENCES achievements(id));
    CREATE TABLE IF NOT EXISTS user_counters(user_id INTEGER NOT NULL, counter_key TEXT NOT NULL, value INTEGER NOT NULL DEFAULT 0, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(user_id,counter_key), FOREIGN KEY(user_id) REFERENCES users(user_id));
    CREATE TABLE IF NOT EXISTS legacy_imports(source_path TEXT NOT NULL, source_user_id INTEGER NOT NULL, payload_json TEXT NOT NULL, imported_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(source_path,source_user_id));
    CREATE INDEX IF NOT EXISTS idx_users_points ON users(points DESC);
    CREATE INDEX IF NOT EXISTS idx_reward_user_created ON reward_events(user_id,created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_processed_user_time ON processed_messages(user_id,processed_at DESC);
    CREATE INDEX IF NOT EXISTS idx_sessions_active ON game_sessions(chat_id,status,ends_at);
    CREATE INDEX IF NOT EXISTS idx_daily_responses ON daily_responses(daily_post_id,user_id);
    CREATE INDEX IF NOT EXISTS idx_user_achievements ON user_achievements(user_id,achievement_id);
    """),
    (2, """
    INSERT OR IGNORE INTO reward_events(user_id,event_type,points_delta,reason,unique_key,metadata_json)
    SELECT u.user_id,'legacy_balance',u.points,'Preserved balance before Qazaq Identity migration','legacy-balance:' || u.user_id,'{"source":"pre_migration_users_points"}'
    FROM users u
    WHERE u.points<>0 AND NOT EXISTS(SELECT 1 FROM reward_events e WHERE e.user_id=u.user_id);
    """),
    (3, """
    UPDATE users SET telegram_id=user_id, activity_points=COALESCE(points,0);
    CREATE UNIQUE INDEX IF NOT EXISTS idx_users_telegram_id ON users(telegram_id);
    CREATE INDEX IF NOT EXISTS idx_users_activity_points ON users(activity_points DESC);
    CREATE INDEX IF NOT EXISTS idx_users_coins ON users(coins DESC);

    CREATE TABLE IF NOT EXISTS coin_transactions(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        game_id INTEGER,
        reference_id TEXT NOT NULL UNIQUE,
        coins_delta INTEGER NOT NULL,
        reason TEXT NOT NULL,
        admin_id INTEGER,
        metadata_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(user_id),
        FOREIGN KEY(game_id) REFERENCES game_sessions(id)
    );
    CREATE UNIQUE INDEX IF NOT EXISTS idx_coin_game_reward ON coin_transactions(game_id) WHERE game_id IS NOT NULL AND coins_delta>0;
    CREATE INDEX IF NOT EXISTS idx_coin_user_created ON coin_transactions(user_id,created_at DESC);

    UPDATE game_questions SET active=0,verified=0;

    UPDATE game_sessions SET topic_id=0 WHERE topic_id IS NULL;
    CREATE UNIQUE INDEX IF NOT EXISTS idx_one_active_game_scope ON game_sessions(chat_id,topic_id) WHERE status='active';
    """),
    (4, """
    UPDATE daily_content SET active=0;
    UPDATE tasks SET active=0;
    CREATE TABLE IF NOT EXISTS scheduled_publications(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        publication_type TEXT NOT NULL,
        publication_date TEXT NOT NULL,
        chat_id INTEGER NOT NULL,
        topic_id INTEGER NOT NULL DEFAULT 0,
        telegram_message_id INTEGER,
        status TEXT NOT NULL DEFAULT 'reserved',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(publication_type,publication_date,chat_id,topic_id)
    );
    """),
    (5, """
    CREATE TABLE IF NOT EXISTS ozgecoin_transactions(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_user_id INTEGER NOT NULL,
        amount INTEGER NOT NULL,
        event_type TEXT NOT NULL,
        reason TEXT NOT NULL,
        unique_key TEXT NOT NULL UNIQUE,
        chat_id INTEGER,
        topic_id INTEGER,
        source_message_id INTEGER,
        admin_id INTEGER,
        metadata_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(telegram_user_id) REFERENCES users(user_id)
    );
    CREATE INDEX IF NOT EXISTS idx_ozgecoin_user_created ON ozgecoin_transactions(telegram_user_id,created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_users_ozgecoins ON users(ozgecoins DESC);

    CREATE TABLE IF NOT EXISTS daily_task_posts(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id TEXT NOT NULL,
        task_date TEXT NOT NULL,
        chat_id INTEGER NOT NULL,
        topic_id INTEGER NOT NULL DEFAULT 0,
        telegram_message_id INTEGER NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(task_date,chat_id,topic_id),
        UNIQUE(chat_id,telegram_message_id)
    );
    CREATE TABLE IF NOT EXISTS daily_task_completions(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_user_id INTEGER NOT NULL,
        task_id TEXT NOT NULL,
        task_date TEXT NOT NULL,
        transaction_id INTEGER NOT NULL UNIQUE,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(telegram_user_id,task_id,task_date),
        FOREIGN KEY(telegram_user_id) REFERENCES users(user_id),
        FOREIGN KEY(transaction_id) REFERENCES ozgecoin_transactions(id)
    );
    CREATE INDEX IF NOT EXISTS idx_daily_task_completion_user_date ON daily_task_completions(telegram_user_id,task_date);

    """),
    (6, """
    DELETE FROM game_answers
    WHERE session_id IN (
        SELECT s.id
        FROM game_sessions s
        JOIN game_questions q ON q.id=s.question_id
        WHERE q.game_type NOT IN ('proverb_finish','true_false','interesting_fact')
    );
    DELETE FROM game_sessions
    WHERE question_id IN (
        SELECT id FROM game_questions
        WHERE game_type NOT IN ('proverb_finish','true_false','interesting_fact')
    );
    DELETE FROM game_questions
    WHERE game_type NOT IN ('proverb_finish','true_false','interesting_fact');
    """),
    (7, """
    DELETE FROM user_achievements;
    DELETE FROM user_counters;
    DELETE FROM achievements;
    """),
]

RESET_TABLES = (
    "user_achievements", "user_counters", "task_submissions", "task_posts", "daily_responses", "daily_posts",
    "scheduled_publications", "game_answers", "coin_transactions", "reward_events", "processed_messages",
    "game_sessions", "daily_task_completions", "daily_task_posts", "ozgecoin_transactions",
)


async def _ensure_user_columns(db) -> None:
    rows = await (await db.execute("PRAGMA table_info(users)")).fetchall()
    existing = {row[1] for row in rows}
    columns = {
        "created_at": "TEXT NOT NULL DEFAULT '1970-01-01 00:00:00'",
        "updated_at": "TEXT NOT NULL DEFAULT '1970-01-01 00:00:00'",
        "last_activity_date": "TEXT",
        "active_days": "INTEGER NOT NULL DEFAULT 0",
        "completed_tasks_count": "INTEGER NOT NULL DEFAULT 0",
        "correct_answers_count": "INTEGER NOT NULL DEFAULT 0",
    }
    for name, definition in columns.items():
        if name not in existing:
            await db.execute(f"ALTER TABLE users ADD COLUMN {name} {definition}")
    await db.execute("UPDATE users SET first_name='' WHERE first_name IS NULL")


async def _ensure_columns(db, table: str, columns: dict[str, str]) -> None:
    rows = await (await db.execute(f"PRAGMA table_info({table})")).fetchall()
    existing = {row[1] for row in rows}
    for name, definition in columns.items():
        if name not in existing:
            await db.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")


async def _ensure_v3_columns(db) -> None:
    await _ensure_columns(db, "users", {
        "telegram_id": "INTEGER",
        "activity_points": "INTEGER NOT NULL DEFAULT 0",
        "coins": "INTEGER NOT NULL DEFAULT 0",
    })
    await _ensure_columns(db, "game_questions", {
        "prompt_kk": "TEXT", "prompt_ru": "TEXT", "options_kk_json": "TEXT", "options_ru_json": "TEXT",
        "answer_text": "TEXT", "accepted_answers_json": "TEXT NOT NULL DEFAULT '[]'", "source_title": "TEXT",
        "source_url": "TEXT", "publisher": "TEXT", "retrieved_at": "TEXT", "verified": "INTEGER NOT NULL DEFAULT 0",
    })
    await _ensure_columns(db, "game_sessions", {"winner_user_id": "INTEGER"})


async def _ensure_v5_columns(db) -> None:
    await _ensure_columns(db, "users", {"ozgecoins": "INTEGER NOT NULL DEFAULT 0"})


async def _reset_production_data_connection(db) -> None:
    for table in RESET_TABLES:
        await db.execute(f"DELETE FROM {table}")
    await db.execute("UPDATE users SET points=0,activity_points=0,coins=0,ozgecoins=0,last_activity_date=NULL,active_days=0,completed_tasks_count=0,correct_answers_count=0,updated_at=CURRENT_TIMESTAMP")


async def reset_production_data(db_path: str | Path) -> None:
    """Clear balances and runtime history while preserving Telegram user rows."""
    async with connect(db_path) as db:
        await db.execute("BEGIN IMMEDIATE")
        await _reset_production_data_connection(db)
        await db.commit()


async def migrate(db_path: str | Path, legacy_db_path: str | Path | None = None) -> None:
    async with connect(db_path) as db:
        await db.execute("CREATE TABLE IF NOT EXISTS schema_migrations(version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)")
        await db.execute("CREATE TABLE IF NOT EXISTS users(user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT NOT NULL DEFAULT '', points INTEGER NOT NULL DEFAULT 0)")
        await _ensure_user_columns(db)
        applied = {row[0] for row in await (await db.execute("SELECT version FROM schema_migrations")).fetchall()}
        for version, script in MIGRATIONS:
            if version not in applied:
                if version == 3:
                    await _ensure_v3_columns(db)
                if version == 5:
                    await _ensure_v5_columns(db)
                await db.executescript(script)
                if version == 5:
                    await _reset_production_data_connection(db)
                await db.execute("INSERT INTO schema_migrations(version) VALUES (?)", (version,))
        await db.commit()
    if legacy_db_path and Path(legacy_db_path).exists() and Path(legacy_db_path).resolve() != Path(db_path).resolve():
        await import_legacy(db_path, legacy_db_path)


async def import_legacy(db_path: str | Path, legacy_path: str | Path) -> None:
    import sqlite3
    source = sqlite3.connect(str(legacy_path))
    source.row_factory = sqlite3.Row
    try:
        table = source.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='users'").fetchone()
        if not table:
            return
        columns = {row[1] for row in source.execute("PRAGMA table_info(users)")}
        rows = source.execute("SELECT * FROM users").fetchall()
    finally:
        source.close()
    async with connect(db_path) as db:
        for row in rows:
            payload = dict(row)
            await db.execute(
                "INSERT OR IGNORE INTO legacy_imports(source_path,source_user_id,payload_json) VALUES(?,?,?)",
                (str(Path(legacy_path).resolve()), payload["user_id"], json.dumps(payload, ensure_ascii=False)),
            )
            # Only a real points column is authoritative. message_count is retained as legacy audit data.
            if "points" in columns:
                await db.execute(
                    "INSERT INTO users(user_id,username,first_name,points) VALUES(?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET username=COALESCE(excluded.username,users.username), first_name=CASE WHEN excluded.first_name<>'' THEN excluded.first_name ELSE users.first_name END, points=MAX(users.points,excluded.points)",
                    (payload["user_id"], payload.get("username"), payload.get("first_name") or "", payload.get("points") or 0),
                )
        await db.commit()
