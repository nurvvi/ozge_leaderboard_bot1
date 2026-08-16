from __future__ import annotations

import json
from html import escape

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.types import CallbackQuery

from app.config import Settings
from app.keyboards import question_keyboard
from app.services.games import answer_game, mark_game_sent, start_game

router = Router()


def format_game_result(game: dict, winner: str) -> str:
    kk_options = json.loads(game["options_kk_json"])
    ru_options = json.loads(game["options_ru_json"])
    safe_winner = escape(winner)
    return (
        f"<b>Ойын аяқталды!</b>\nЖеңімпаз: {safe_winner}\nСыйлық: +3 ÖZGEcoins\n"
        f"Дұрыс жауап: {escape(kk_options[game['correct_index']])}\n\n"
        f"<b>Игра завершена!</b>\nПобедитель: {safe_winner}\nНаграда: +3 ÖZGEcoins\n"
        f"Правильный ответ: {escape(ru_options[game['correct_index']])}"
    )


@router.callback_query(F.data.startswith("game:start:"))
async def game_start(callback: CallbackQuery, db_path: str, settings: Settings) -> None:
    if not callback.from_user or not callback.message:
        return
    game_type = callback.data.rsplit(":", 1)[-1]
    try:
        game = await start_game(db_path, game_type, callback.message.chat.id, callback.message.message_thread_id, settings.game_duration_minutes, callback.from_user.id)
    except ValueError as exc:
        await callback.answer(str(exc), show_alert=True); return
    sent = await callback.message.answer(
        f"<b>{game['prompt_kk']}</b>\nБірінші дұрыс жауапқа +3 ÖZGEcoins.\n\n<b>{game['prompt_ru']}</b>\nПервый правильный ответ получит +3 ÖZGEcoins.",
        reply_markup=question_keyboard(game["session_id"], game["options_kk_json"], game["options_ru_json"]), parse_mode=ParseMode.HTML,
    )
    await mark_game_sent(db_path, game["session_id"], sent.message_id)
    await callback.answer()


@router.callback_query(F.data.startswith("game:answer:"))
async def game_answer(callback: CallbackQuery, db_path: str) -> None:
    if not callback.from_user:
        return
    _, _, session, selected = callback.data.split(":")
    result, game = await answer_game(db_path, int(session), {"id": callback.from_user.id, "username": callback.from_user.username, "first_name": callback.from_user.first_name}, int(selected))
    if result.reason == "duplicate":
        await callback.answer("Жауап қабылданған / Ответ уже принят", show_alert=True)
    elif result.reason == "closed":
        await callback.answer("Ойын аяқталды / Игра завершена", show_alert=True)
    elif result.won:
        await callback.answer("Дұрыс! +3 ÖZGEcoins / Правильно! +3 ÖZGEcoins", show_alert=True)
        winner = "@" + callback.from_user.username if callback.from_user.username else callback.from_user.first_name
        await callback.message.answer(format_game_result(game, winner), parse_mode=ParseMode.HTML)
    else:
        await callback.answer("Қате, тағы бір қатысушы жауап бере алады / Неверно, другой участник ещё может ответить", show_alert=True)
