from __future__ import annotations

import json

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup


def main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="👤 Менің рейтингім / Мой рейтинг"), KeyboardButton(text="🏆 Көшбасшылар / Лидерборд")],
        [KeyboardButton(text="📅 Күн тапсырмасы / Задание дня"), KeyboardButton(text="🎮 Ойындар / Игры")],
        [KeyboardButton(text="ℹ️ Ережелер / Правила")],
    ], resize_keyboard=True)


def games_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Мақалды жалғастыр / Продолжи пословицу", callback_data="game:start:proverb_finish")],
        [InlineKeyboardButton(text="Дұрыс па, бұрыс па? / Правда или ложь?", callback_data="game:start:true_false")],
        [InlineKeyboardButton(text="Қызықты факт / Интересный факт", callback_data="game:start:interesting_fact")],
    ])


def question_keyboard(session_id: int, options_kk_json: str, options_ru_json: str) -> InlineKeyboardMarkup:
    kk = json.loads(options_kk_json or "[]")
    ru = json.loads(options_ru_json or "[]")
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"{chr(65+i)}. {option} / {ru[i] if i < len(ru) else option}", callback_data=f"game:answer:{session_id}:{i}")] for i, option in enumerate(kk)])
