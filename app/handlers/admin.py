from __future__ import annotations

from html import escape

from aiogram import Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message

from app.config import Settings, telegram_thread_id
from app.keyboards import question_keyboard
from app.services.games import cancel_game, mark_game_sent, start_game
from app.services.rewards import award_ozgecoins
from app.services.users import get_profile

router = Router()


def allowed(message: Message, settings: Settings) -> bool:
    return bool(message.from_user and message.from_user.id in settings.admin_ids)


async def deny(message: Message, settings: Settings) -> bool:
    if allowed(message, settings):
        return False
    await message.answer("Команда тек әкімшіге қолжетімді.\n\nКоманда доступна только администратору.")
    return True


@router.message(Command("admin"))
async def admin(message: Message, settings: Settings) -> None:
    if await deny(message, settings): return
    await message.answer("🛠 <b>Әкімші мәзірі</b>\n\n<b>Admin menu</b>\n\n/award telegram_id amount reason\n/deduct telegram_id amount reason\n/reset_points telegram_id reason\n/user_info telegram_id\n/cancel_game\n/start_game game_type", parse_mode=ParseMode.HTML)


@router.message(Command("start_game"))
async def start_game_command(message: Message, db_path: str, settings: Settings) -> None:
    if await deny(message, settings): return
    args = (message.text or "").split()
    kind = args[1] if len(args) > 1 else "proverb_finish"
    try:
        game = await start_game(db_path, kind, settings.flood_chat_id, settings.flood_topic_id, settings.game_duration_minutes, message.from_user.id)
    except ValueError as exc:
        await message.answer(str(exc)); return
    sent = await message.bot.send_message(
        settings.flood_chat_id,
        f"🎮 <b>{escape(game['prompt_kk'])}</b>\n\n<b>{escape(game['prompt_ru'])}</b>",
        message_thread_id=telegram_thread_id(settings.flood_topic_id),
        reply_markup=question_keyboard(game["session_id"], game["options_kk_json"], game["options_ru_json"]),
        parse_mode=ParseMode.HTML,
    )
    await mark_game_sent(db_path, game["session_id"], sent.message_id)


async def _manual_reward(message: Message, db_path: str, settings: Settings, sign: int) -> None:
    if await deny(message, settings): return
    parts = (message.text or "").split(maxsplit=3)
    if len(parts) < 4:
        await message.answer("/award telegram_id amount reason"); return
    try:
        telegram_id, amount = int(parts[1]), abs(int(parts[2])) * sign
    except ValueError:
        await message.answer("telegram_id және amount сан болуы керек / должны быть числами"); return
    result = await award_ozgecoins(db_path, telegram_id, amount, "admin_adjustment", parts[3], admin_id=message.from_user.id, unique_key=f"admin:{message.chat.id}:{message.message_id}")
    await message.answer(f"{result.new_balance} ÖZGEcoins")


@router.message(Command("award"))
async def award(message: Message, db_path: str, settings: Settings) -> None:
    await _manual_reward(message, db_path, settings, 1)


@router.message(Command("deduct"))
async def deduct(message: Message, db_path: str, settings: Settings) -> None:
    await _manual_reward(message, db_path, settings, -1)


@router.message(Command("award_coins"))
async def award_coins(message: Message, db_path: str, settings: Settings) -> None:
    await _manual_reward(message, db_path, settings, 1)


@router.message(Command("reset_points"))
async def reset_points(message: Message, db_path: str, settings: Settings) -> None:
    if await deny(message, settings): return
    parts = (message.text or "").split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("/reset_points telegram_id reason"); return
    try:
        telegram_id = int(parts[1])
    except ValueError:
        await message.answer("telegram_id сан болуы керек / должен быть числом"); return
    reason = parts[2]
    row = await get_profile(db_path, telegram_id)
    if not row:
        await message.answer("Пайдаланушы табылмады.\n\nПользователь не найден."); return
    if row["ozgecoins"]:
        await award_ozgecoins(db_path, telegram_id, -row["ozgecoins"], "admin_reset", reason, admin_id=message.from_user.id, unique_key=f"reset:{message.message_id}:{telegram_id}")
    await message.answer("Баланс өтемдік транзакциялармен қалпына келтірілді.\n\nБаланс сброшен компенсирующими транзакциями.")


@router.message(Command("user_info"))
async def user_info(message: Message, db_path: str, settings: Settings) -> None:
    if await deny(message, settings): return
    try: telegram_id = int((message.text or "").split()[1])
    except (ValueError, IndexError): await message.answer("/user_info telegram_id"); return
    row = await get_profile(db_path, telegram_id)
    await message.answer("Пайдаланушы табылмады.\n\nПользователь не найден." if not row else f"telegram_id={telegram_id}\nÖZGEcoins={row['ozgecoins']}")


@router.message(Command("cancel_game"))
async def cancel_game_command(message: Message, db_path: str, settings: Settings) -> None:
    if await deny(message, settings): return
    cancelled = await cancel_game(db_path, settings.flood_chat_id, settings.flood_topic_id)
    await message.answer("Ойын тоқтатылды.\n\nИгра отменена." if cancelled else "Белсенді ойын жоқ.\n\nАктивной игры нет.")
