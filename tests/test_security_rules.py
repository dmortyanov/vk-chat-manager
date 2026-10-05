import sys
from pathlib import Path
from types import SimpleNamespace

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Добавляем корневую директорию проекта в sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.security_rules import (
    SECURITY_RULES,
    normalize_action,
    format_rules_menu,
    get_effective_rule_action,
    check_message_violations
)


def test_rule_defaults():
    assert len(SECURITY_RULES) == 24, f"Ожидалось 24 правила, найдено {len(SECURITY_RULES)}"
    assert SECURITY_RULES["инвайт"].default_action == "пред"
    assert SECURITY_RULES["банворд"].default_action == "кик"
    assert SECURITY_RULES["банстикер"].default_action == "пред"
    assert SECURITY_RULES["макспреды"].default_action == "бан"
    assert SECURITY_RULES["фото"].default_action == "разрешено"
    assert SECURITY_RULES["мат"].default_action == "разрешено"
    assert SECURITY_RULES["ссылка"].default_action == "разрешено"
    print("✅ Дефолтные настройки правил ТЗ: OK")


def test_action_normalization():
    assert normalize_action("пред") == "пред"
    assert normalize_action("варн") == "пред"
    assert normalize_action("кик") == "кик"
    assert normalize_action("kick") == "кик"
    assert normalize_action("мут") == "мут"
    assert normalize_action("бан") == "бан"
    assert normalize_action("разрешено") == "разрешено"
    assert normalize_action("выкл") == "разрешено"
    print("✅ Нормализация действий и алиасов: OK")


def test_format_rules_menu():
    custom = {"ссылка": "мут", "фото": "кик"}
    menu_text = format_rules_menu(custom)
    assert "Вложения:" in menu_text
    assert "Посты и ссылки:" in menu_text
    assert "Действия:" in menu_text
    assert "Нарушения:" in menu_text
    assert "🌐 Ссылки в сообщении: 🔇 мут (ссылка)" in menu_text
    assert "🏞️ Фотография: ❌ кик (фото)" in menu_text
    assert "💬 Ссылка на чат: ⚠️ пред (инвайт)" in menu_text
    print("✅ Генерация текста меню запретов: OK")


def test_violations_detection():
    custom_rules = {
        "ссылка": "мут",
        "инвайт": "пред",
        "капс": "кик",
        "банворд": "кик",
        "мат": "пред",
        "фото": "кик",
    }
    banwords = ["реклама", "казино"]

    # 1. Проверка обычной ссылки
    msg_link = SimpleNamespace(text="Заходи сюда https://example.com!", attachments=[])
    viol = check_message_violations(msg_link, custom_rules, banwords)
    assert viol is not None
    assert viol[0] == "ссылка" and viol[1] == "мут"

    # 2. Проверка ссылки-инвайта в беседу
    msg_invite = SimpleNamespace(text="Вступайте в чат https://vk.me/join/AJQ1d...", attachments=[])
    viol = check_message_violations(msg_invite, custom_rules, banwords)
    assert viol is not None
    assert viol[0] == "инвайт" and viol[1] == "пред"

    # 3. Проверка капса
    msg_caps = SimpleNamespace(text="ВСЕМ ПРИВЕТ КАК ДЕЛА", attachments=[])
    viol = check_message_violations(msg_caps, custom_rules, banwords)
    assert viol is not None
    assert viol[0] == "капс" and viol[1] == "кик"

    # 4. Проверка банворда
    msg_bw = SimpleNamespace(text="У нас тут лучшее онлайн казино мира", attachments=[])
    viol = check_message_violations(msg_bw, custom_rules, banwords)
    assert viol is not None
    assert viol[0] == "банворд" and viol[1] == "кик"

    # 5. Проверка мата
    msg_mat = SimpleNamespace(text="Да пошел ты на хуй отсюда", attachments=[])
    viol = check_message_violations(msg_mat, custom_rules, banwords)
    assert viol is not None
    assert viol[0] == "мат" and viol[1] == "пред"

    # 6. Проверка вложения фото
    att_photo = SimpleNamespace(type="photo")
    msg_photo = SimpleNamespace(text="Вот фотка", attachments=[att_photo])
    viol = check_message_violations(msg_photo, custom_rules, banwords)
    assert viol is not None
    assert viol[0] == "фото" and viol[1] == "кик"

    # 7. Проверка стикера (по умолчанию разрешен)
    att_sticker = SimpleNamespace(type="sticker")
    msg_sticker = SimpleNamespace(text="", attachments=[att_sticker])
    viol = check_message_violations(msg_sticker, {}, [])
    assert viol is None, f"Expected sticker to be allowed by default, got violation: {viol}"

    # 7.1. Проверка стикера при установленном запрете
    viol_banned_sticker = check_message_violations(msg_sticker, {"стикеры": "мут"}, [])
    assert viol_banned_sticker is not None and viol_banned_sticker[0] == "стикеры" and viol_banned_sticker[1] == "мут"

    # 8. Чистое сообщение
    msg_clean = SimpleNamespace(text="Привет, как дела друзья?", attachments=[])
    viol = check_message_violations(msg_clean, custom_rules, banwords)
    assert viol is None

    print("✅ Детекция нарушений в сообщениях: OK")


if __name__ == "__main__":
    print("🧪 Запуск тестов модуля правил безопасности...")
    test_rule_defaults()
    test_action_normalization()
    test_format_rules_menu()
    test_violations_detection()
    print("\n🎉 Все тесты правил безопасности успешно пройдены!")
