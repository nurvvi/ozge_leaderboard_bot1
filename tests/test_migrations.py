import sqlite3

import pytest

from app.database import connect
from app.migrations import migrate


@pytest.mark.asyncio
async def test_migration_preserves_points_and_is_idempotent(tmp_path):
    path = tmp_path / "old.db"
    old = sqlite3.connect(path)
    old.execute("CREATE TABLE users(user_id INTEGER PRIMARY KEY,username TEXT,first_name TEXT,points INTEGER DEFAULT 0)")
    old.execute("INSERT INTO users VALUES(1,'qazaq','Aruzhan',42)")
    old.commit(); old.close()
    await migrate(path); await migrate(path)
    async with connect(path) as db:
        user = await (await db.execute("SELECT points,activity_points,coins,ozgecoins,telegram_id FROM users WHERE user_id=1")).fetchone()
        versions = await (await db.execute("SELECT COUNT(*) FROM schema_migrations")).fetchone()
    assert tuple(user) == (0, 0, 0, 0, 1)
    assert versions[0] == 7


@pytest.mark.asyncio
async def test_legacy_message_count_is_audited_not_added(tmp_path):
    main, legacy = tmp_path / "main.db", tmp_path / "legacy.db"
    await migrate(main)
    source = sqlite3.connect(legacy)
    source.execute("CREATE TABLE users(user_id INTEGER PRIMARY KEY,username TEXT,first_name TEXT,message_count INTEGER)")
    source.execute("INSERT INTO users VALUES(2,'x','X',900)"); source.commit(); source.close()
    await migrate(main, legacy); await migrate(main, legacy)
    async with connect(main) as db:
        audits = await (await db.execute("SELECT COUNT(*) FROM legacy_imports")).fetchone()
        user = await (await db.execute("SELECT points FROM users WHERE user_id=2")).fetchone()
    assert audits[0] == 1
    assert user is None


@pytest.mark.asyncio
async def test_production_reset_keeps_users_and_clears_state(tmp_path):
    path = tmp_path / "reset.db"
    await migrate(path)
    async with connect(path) as db:
        await db.execute("INSERT INTO users(user_id,telegram_id,username,first_name,ozgecoins) VALUES(7,7,'user','User',25)")
        tx = await db.execute("INSERT INTO ozgecoin_transactions(telegram_user_id,amount,event_type,reason,unique_key) VALUES(7,25,'test','test','test:7')")
        await db.execute("INSERT INTO daily_task_completions(telegram_user_id,task_id,task_date,transaction_id) VALUES(7,'task','2026-08-08',?)", (tx.lastrowid,))
        question = await db.execute("INSERT INTO game_questions(external_id,game_type,prompt,options_json,correct_index,explanation) VALUES('reset-q','proverb_finish','Q','[]',0,'E')")
        await db.execute("INSERT INTO game_sessions(question_id,chat_id,topic_id,ends_at) VALUES(?,-1001,5,'2099-01-01 00:00:00')", (question.lastrowid,))
        await db.execute("DELETE FROM schema_migrations WHERE version=5")
        await db.commit()
    await migrate(path)
    async with connect(path) as db:
        user = await (await db.execute("SELECT ozgecoins FROM users WHERE telegram_id=7")).fetchone()
        counts = await (await db.execute("SELECT (SELECT COUNT(*) FROM ozgecoin_transactions),(SELECT COUNT(*) FROM daily_task_completions),(SELECT COUNT(*) FROM game_sessions)")).fetchone()
    assert user[0] == 0
    assert tuple(counts) == (0, 0, 0)
