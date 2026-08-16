from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.config import normalize_topic_id
from app.database import connect
from app.services.rewards import award_in_transaction

GAME_TYPES = {"proverb_finish", "true_false", "interesting_fact"}
COIN_REWARD = 3


@dataclass
class GameAnswerResult:
    accepted: bool
    correct: bool
    won: bool
    ozgecoins: int
    reason: str | None = None


async def start_game(db_path: str | Path, game_type: str, chat_id: int, topic_id: int | None, duration_minutes: int, created_by: int | None = None) -> dict:
    if game_type not in GAME_TYPES:
        raise ValueError("Белгісіз ойын / Неизвестная игра")
    topic = normalize_topic_id(topic_id)
    async with connect(db_path) as db:
        await db.execute("BEGIN IMMEDIATE")
        active = await (await db.execute("SELECT id FROM game_sessions WHERE chat_id=? AND topic_id=? AND status='active' AND ends_at>CURRENT_TIMESTAMP", (chat_id, topic))).fetchone()
        if active:
            await db.rollback(); raise ValueError("Бұл тақырыпта ойын жүріп жатыр / В этой теме уже идёт игра")
        question = await (await db.execute(
            """SELECT * FROM game_questions WHERE game_type=? AND active=1 AND verified=1
            AND source_url IS NOT NULL AND source_url<>'' ORDER BY RANDOM() LIMIT 1""", (game_type,)
        )).fetchone()
        if not question:
            await db.rollback(); raise ValueError("Тексерілген сұрақ жоқ / Нет проверенных вопросов")
        ends = (datetime.now(timezone.utc) + timedelta(minutes=duration_minutes)).strftime("%Y-%m-%d %H:%M:%S")
        try:
            cursor = await db.execute("INSERT INTO game_sessions(question_id,chat_id,topic_id,ends_at,created_by) VALUES(?,?,?,?,?)", (question["id"], chat_id, topic, ends, created_by))
            await db.commit()
        except Exception:
            await db.rollback(); raise ValueError("Бұл тақырыпта ойын жүріп жатыр / В этой теме уже идёт игра")
        result = dict(question); result["session_id"] = cursor.lastrowid; result["ends_at"] = ends
        return result


async def mark_game_sent(db_path: str | Path, session_id: int, message_id: int) -> None:
    async with connect(db_path) as db:
        await db.execute("UPDATE game_sessions SET telegram_message_id=? WHERE id=?", (message_id, session_id)); await db.commit()


async def answer_game(db_path: str | Path, session_id: int, user: dict, selected_index: int) -> tuple[GameAnswerResult, dict]:
    async with connect(db_path) as db:
        await db.execute("BEGIN IMMEDIATE")
        row = await (await db.execute(
            """SELECT s.*,q.game_type,q.correct_index,q.explanation,q.options_kk_json,q.options_ru_json,
            q.source_title,q.source_url FROM game_sessions s JOIN game_questions q ON q.id=s.question_id
            WHERE s.id=? AND s.status='active' AND s.ends_at>CURRENT_TIMESTAMP""", (session_id,)
        )).fetchone()
        if not row:
            await db.rollback(); return GameAnswerResult(False, False, False, 0, "closed"), {}
        correct = selected_index == row["correct_index"]
        try:
            await db.execute("INSERT INTO game_answers(session_id,user_id,selected_index,is_correct) VALUES(?,?,?,?)", (session_id, user["id"], selected_index, int(correct)))
        except Exception:
            await db.rollback(); return GameAnswerResult(False, False, False, 0, "duplicate"), dict(row)
        if not correct:
            await db.commit(); return GameAnswerResult(True, False, False, 0, "incorrect"), dict(row)
        closed = await db.execute("UPDATE game_sessions SET status='finished',winner_user_id=? WHERE id=? AND status='active'", (user["id"], session_id))
        if not closed.rowcount:
            await db.rollback(); return GameAnswerResult(False, True, False, 0, "closed"), dict(row)
        reward = await award_in_transaction(
            db, user["id"], COIN_REWARD, "game_win", "First correct game answer", f"game-winner:{session_id}",
            username=user.get("username"), first_name=user.get("first_name", ""), chat_id=row["chat_id"],
            topic_id=row["topic_id"], metadata={"game_id": session_id, "game_type": row["game_type"]},
        )
        if not reward.awarded:
            await db.rollback(); return GameAnswerResult(False, True, False, 0, "duplicate_reward"), dict(row)
        await db.execute("UPDATE game_answers SET points_awarded=? WHERE session_id=? AND user_id=?", (COIN_REWARD, session_id, user["id"]))
        await db.commit()
        return GameAnswerResult(True, True, True, reward.new_balance), dict(row)


async def close_expired_games(db_path: str | Path) -> list[dict]:
    async with connect(db_path) as db:
        rows = await (await db.execute("""SELECT s.id,s.chat_id,s.topic_id,q.prompt_kk,q.prompt_ru,q.correct_index,q.options_kk_json,q.options_ru_json,q.explanation,q.source_title,q.source_url,
            SUM(CASE WHEN a.is_correct=1 THEN 1 ELSE 0 END) correct_count,SUM(CASE WHEN a.is_correct=0 THEN 1 ELSE 0 END) wrong_count
            FROM game_sessions s JOIN game_questions q ON q.id=s.question_id LEFT JOIN game_answers a ON a.session_id=s.id
            WHERE s.status='active' AND s.ends_at<=CURRENT_TIMESTAMP GROUP BY s.id""")).fetchall()
        if rows:
            await db.executemany("UPDATE game_sessions SET status='expired' WHERE id=? AND status='active'", [(row["id"],) for row in rows]); await db.commit()
        return [dict(row) for row in rows]


async def cancel_game(db_path: str | Path, chat_id: int, topic_id: int | None = None) -> bool:
    async with connect(db_path) as db:
        cursor = await db.execute("UPDATE game_sessions SET status='cancelled' WHERE chat_id=? AND topic_id=? AND status='active'", (chat_id, normalize_topic_id(topic_id))); await db.commit(); return bool(cursor.rowcount)
