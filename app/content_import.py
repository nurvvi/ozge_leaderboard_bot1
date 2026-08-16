from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from urllib.parse import urlparse

from app.database import connect
from app.migrations import migrate

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
GAME_FILES = ("proverbs.json", "facts.json", "quiz_questions.json")


def load_json(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"{path.name}: root must be a JSON array")
    return data


def is_playable(entry: dict) -> bool:
    url = str(entry.get("source_url") or "")
    return bool(entry.get("verified") is True and entry.get("active") is True and urlparse(url).scheme == "https" and urlparse(url).netloc)


def validate_entry(entry: dict, filename: str) -> None:
    required = ({"id", "type", "kk", "ru", "reward", "active"} if filename == "daily_tasks.json" else
                {"id", "kk", "ru", "source_title", "source_url", "publisher", "retrieved_at", "verified", "active"})
    missing = sorted(required - entry.keys())
    if missing:
        raise ValueError(f"{filename}:{entry.get('id','?')} missing {', '.join(missing)}")
    if filename != "daily_tasks.json" and "answer" not in entry:
        raise ValueError(f"{filename}:{entry['id']} missing answer")


def to_questions(filename: str, entry: dict) -> list[dict]:
    base = {
        "prompt_kk": entry["kk"], "prompt_ru": entry["ru"],
        "options_kk": entry.get("options_kk", []), "options_ru": entry.get("options_ru", []),
        "correct_index": int(entry.get("correct_index", 0)), "answer_text": str(entry.get("answer", "")),
        "accepted_answers": entry.get("accepted_answers", []), "explanation": entry.get("explanation_ru", entry["ru"]),
        "source_title": entry["source_title"], "source_url": entry["source_url"], "publisher": entry["publisher"],
        "retrieved_at": entry["retrieved_at"], "verified": int(is_playable(entry)), "active": int(is_playable(entry)),
    }
    if filename == "proverbs.json":
        types = ("proverb_finish",)
    elif filename == "facts.json":
        types = ("true_false", "interesting_fact")
    else:
        types = ()
    return [{**base, "external_id": f"sourced:{game_type}:{entry['id']}", "game_type": game_type} for game_type in types]


async def import_content(db_path: str | Path, data_dir: Path = DATA_DIR, legacy_db_path: str | Path | None = None) -> dict[str, int]:
    # Ensure database schema is initialized before importing
    await migrate(db_path, legacy_db_path)

    counts = {"questions": 0, "tasks": 0, "rejected": 0}
    async with connect(db_path) as db:
        for filename in GAME_FILES:
            for entry in load_json(data_dir / filename):
                validate_entry(entry, filename)
                if not is_playable(entry):
                    counts["rejected"] += 1
                for question in to_questions(filename, entry):
                    await db.execute(
                        """INSERT INTO game_questions(external_id,game_type,prompt,options_json,correct_index,explanation,reward_points,active,prompt_kk,prompt_ru,options_kk_json,options_ru_json,answer_text,accepted_answers_json,source_title,source_url,publisher,retrieved_at,verified)
                        VALUES(?,?,?,?,?,?,3,?,?,?,?,?,?,?,?,?,?,?,?)
                        ON CONFLICT(external_id) DO UPDATE SET game_type=excluded.game_type,prompt=excluded.prompt,options_json=excluded.options_json,correct_index=excluded.correct_index,explanation=excluded.explanation,reward_points=3,active=excluded.active,prompt_kk=excluded.prompt_kk,prompt_ru=excluded.prompt_ru,options_kk_json=excluded.options_kk_json,options_ru_json=excluded.options_ru_json,answer_text=excluded.answer_text,accepted_answers_json=excluded.accepted_answers_json,source_title=excluded.source_title,source_url=excluded.source_url,publisher=excluded.publisher,retrieved_at=excluded.retrieved_at,verified=excluded.verified""",
                        (question["external_id"], question["game_type"], question["prompt_kk"], json.dumps(question["options_kk"], ensure_ascii=False), question["correct_index"], question["explanation"], question["active"], question["prompt_kk"], question["prompt_ru"], json.dumps(question["options_kk"], ensure_ascii=False), json.dumps(question["options_ru"], ensure_ascii=False), question["answer_text"], json.dumps(question["accepted_answers"], ensure_ascii=False), question["source_title"], question["source_url"], question["publisher"], question["retrieved_at"], question["verified"]),
                    )
                    counts["questions"] += 1
        tasks = load_json(data_dir / "daily_tasks.json")
        for entry in tasks:
            validate_entry(entry, "daily_tasks.json")
            counts["tasks"] += 1
        await db.commit()
    return counts


async def _main() -> None:
    parser = argparse.ArgumentParser(description="Validate and import locally reviewed game content")
    parser.add_argument("--db", default="activity_bot.db")
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--legacy-db", type=Path, default=None, help="Optional legacy database to import from")
    args = parser.parse_args()
    print(await import_content(args.db, args.data_dir, args.legacy_db))


if __name__ == "__main__":
    asyncio.run(_main())
