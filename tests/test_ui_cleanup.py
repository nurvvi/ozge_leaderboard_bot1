from pathlib import Path

from app.bot_commands import BOT_COMMANDS, LANGUAGE_CODES, command_scopes
from app.keyboards import games_menu
from app.services.games import GAME_TYPES


def test_only_supported_games_are_available():
    expected = {"proverb_finish", "true_false", "interesting_fact"}
    callbacks = {
        button.callback_data.removeprefix("game:start:")
        for row in games_menu().inline_keyboard
        for button in row
    }
    assert GAME_TYPES == expected
    assert callbacks == expected


def test_main_menu_has_no_achievements_entry():
    from app.keyboards import main_keyboard

    rows = [[button.text for button in row] for row in main_keyboard().keyboard]
    assert rows == [
        ["👤 Менің рейтингім / Мой рейтинг", "🏆 Көшбасшылар / Лидерборд"],
        ["📅 Күн тапсырмасы / Задание дня", "🎮 Ойындар / Игры"],
        ["ℹ️ Ережелер / Правила"],
    ]
    labels = {label for row in rows for label in row}
    forbidden = ("\u0416\u0435\u0442\u0456\u0441\u0442\u0456\u043a\u0442\u0435\u0440", "\u0414\u043e\u0441\u0442\u0438\u0436\u0435\u043d\u0438\u044f")
    assert all(term not in label for label in labels for term in forbidden)


def test_achievements_command_and_user_facing_names_are_absent():
    project_dir = Path(__file__).resolve().parents[1]
    text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (project_dir / "main.py", project_dir / "app" / "keyboards.py", project_dir / "app" / "handlers" / "common.py")
    )
    forbidden = (
        "\u0416\u0435\u0442\u0456\u0441\u0442\u0456\u043a\u0442\u0435\u0440",
        "\u0414\u043e\u0441\u0442\u0438\u0436\u0435\u043d\u0438\u044f",
        "\u041c\u0430\u049b\u0430\u043b \u0448\u0435\u0431\u0435\u0440\u0456",
        "\u049a\u0430\u0437\u0430\u049b\u0448\u0430 \u0441\u04e9\u0439\u043b\u0435\u0439\u043c\u0456\u043d",
        "Storyteller",
        "Local Explorer",
        "\u0411\u0456\u0440\u043b\u0456\u043a \u043a\u04af\u0448\u0456",
        'command="achievements"',
    )
    assert all(term not in text for term in forbidden)


def test_registered_command_menu_has_no_achievement_aliases():
    blocked = {"achievements", "achievement", "badges", "badge"}
    registered = {item.command for item in BOT_COMMANDS}
    assert registered == {"start", "help", "profile", "top", "daily", "games", "admin", "where"}
    assert registered.isdisjoint(blocked)
    blocked_labels = ("\u0416\u0435\u0442\u0456\u0441\u0442\u0456\u043a\u0442\u0435\u0440", "\u0414\u043e\u0441\u0442\u0438\u0436\u0435\u043d\u0438\u044f")
    assert all(label not in item.description for item in BOT_COMMANDS for label in blocked_labels)


def test_command_reset_covers_all_required_scopes_and_languages():
    scopes = {scope.type for scope in command_scopes(-1001)}
    assert scopes == {
        "default",
        "all_private_chats",
        "all_group_chats",
        "all_chat_administrators",
        "chat",
        "chat_administrators",
    }
    assert LANGUAGE_CODES == (None, "ru", "kk")


def test_user_facing_python_has_no_country_flags_or_coin_emojis():
    app_dir = Path(__file__).resolve().parents[1] / "app"
    user_facing = [
        app_dir / "handlers" / "activity.py",
        app_dir / "handlers" / "admin.py",
        app_dir / "handlers" / "common.py",
        app_dir / "handlers" / "daily.py",
        app_dir / "handlers" / "games.py",
        app_dir / "keyboards.py",
        app_dir / "scheduler.py",
        app_dir / "services" / "daily_tasks.py",
    ]
    text = "\n".join(path.read_text(encoding="utf-8") for path in user_facing)
    for forbidden in ("\U0001f1f0\U0001f1ff", "\U0001f1f7\U0001f1fa", "\U0001f319", "\U0001fa99"):
        assert forbidden not in text
