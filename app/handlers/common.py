from __future__ import annotations

from aiogram import F, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message

from app.keyboards import games_menu, main_keyboard
from app.services.users import display_name, get_profile, get_top, render_top, upsert_user

router = Router()

HELP = """<b>ÖZGEcoins</b>
Мәтін +1, фото +3, видео/дауыс/дөңгелек +5, ойын жеңісі +3 ÖZGEcoins. Күн тапсырмасының сыйлығы тапсырмада көрсетіледі.

<b>ÖZGEcoins</b>
Текст +1, фото +3, видео/голосовое/кружок +5, победа в игре +3 ÖZGEcoins. Награда задания дня указана в самом задании."""


@router.message(Command("start"))
async def start(message: Message, db_path: str) -> None:
    if message.from_user:
        await upsert_user(db_path, message.from_user.id, message.from_user.username, message.from_user.first_name)
    await message.answer("Сәлем!\nÖZGEcoins жинап, форумда сыйлықтар ал! 🎁\n\nПривет!\nЗарабатывай ÖZGEcoins и получай подарки на форуме! 🎁", reply_markup=main_keyboard())


@router.message(Command("help"))
@router.message(F.text == "ℹ️ Ережелер / Правила")
async def help_command(message: Message) -> None:
    await message.answer(HELP, parse_mode=ParseMode.HTML)


@router.message(Command("where"))
async def where(message: Message) -> None:
    topic_id = message.message_thread_id or 0
    await message.answer(
        f"Осы хабарламаның идентификаторлары:\nchat_id: <code>{message.chat.id}</code>\nmessage_thread_id: <code>{topic_id}</code>\n\n"
        f"Идентификаторы этого сообщения:\nchat_id: <code>{message.chat.id}</code>\nmessage_thread_id: <code>{topic_id}</code>",
        parse_mode=ParseMode.HTML,
    )


@router.message(Command("top"))
@router.message(F.text == "🏆 Көшбасшылар / Лидерборд")
async def top(message: Message, db_path: str) -> None:
    await message.answer(render_top(await get_top(db_path)), parse_mode=ParseMode.HTML)


@router.message(Command("profile"))
@router.message(Command("rating"))
@router.message(F.text == "👤 Менің рейтингім / Мой рейтинг")
async def profile(message: Message, db_path: str) -> None:
    if not message.from_user:
        return
    await upsert_user(db_path, message.from_user.id, message.from_user.username, message.from_user.first_name)
    row = await get_profile(db_path, message.from_user.id)
    text = f"👤 <b>{display_name(row)}</b>\n\n<b>{row['ozgecoins']} ÖZGEcoins</b>"
    await message.answer(text, parse_mode=ParseMode.HTML)


@router.message(Command("games"))
@router.message(F.text == "🎮 Ойындар / Игры")
async def games(message: Message) -> None:
    await message.answer("🎮 <b>Ойынды таңда</b>\n\n<b>Выбери игру</b>", reply_markup=games_menu(), parse_mode=ParseMode.HTML)
