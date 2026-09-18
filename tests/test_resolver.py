import sys
from pathlib import Path
import asyncio

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from unittest.mock import AsyncMock, MagicMock
from utils.resolver import resolve_target_and_args
from utils.formatters import format_duration, plural_ru


async def run_resolver_tests():
    print("🧪 Запуск тестов модуля resolver & formatters...")

    mock_api = AsyncMock()

    # 1. Тест ответа на сообщение (reply)
    msg_reply = MagicMock()
    msg_reply.text = "/warn Спам в чате"
    msg_reply.reply_message = MagicMock()
    msg_reply.reply_message.from_id = 12345678
    msg_reply.fwd_messages = []

    target, args = await resolve_target_and_args(msg_reply, mock_api, command_name="warn")
    assert target == 12345678, f"Target должен быть 12345678, получено {target}"
    assert args == "Спам в чате", f"Args должен быть 'Спам в чате', получено '{args}'"
    print("✅ Определение цели по reply_message: OK")

    # 2. Тест упоминания [id12345|Имя Фамилия]
    msg_mention = MagicMock()
    msg_mention.text = "/kick [id98765|Иван Иванов] Оскорбления"
    msg_mention.reply_message = None
    msg_mention.fwd_messages = []

    target, args = await resolve_target_and_args(msg_mention, mock_api, command_name="kick")
    assert target == 98765, f"Target должен быть 98765, получено {target}"
    assert args == "Оскорбления", f"Args должен быть 'Оскорбления', получено '{args}'"
    print("✅ Определение цели по [id...|Имя]: OK")

    # 3. Тест чистого id12345 или 12345
    msg_id = MagicMock()
    msg_id.text = "!mute id55555 30m Флуд"
    msg_id.reply_message = None
    msg_id.fwd_messages = []

    target, args = await resolve_target_and_args(msg_id, mock_api, command_name="mute")
    assert target == 55555, f"Target должен быть 55555, получено {target}"
    assert args == "30m Флуд", f"Args должен быть '30m Флуд', получено '{args}'"
    print("✅ Определение цели по id55555: OK")

    # 3.1 Тест русской команды с @id12345
    msg_ru_at = MagicMock()
    msg_ru_at.text = "/мут @id123456789 15m спам"
    msg_ru_at.reply_message = None
    msg_ru_at.fwd_messages = []

    target, args = await resolve_target_and_args(msg_ru_at, mock_api, command_name="mute")
    assert target == 123456789, f"Target должен быть 123456789, получено {target}"
    assert args == "15m спам", f"Args должен быть '15m спам', получено '{args}'"
    print("✅ Русская команда /мут с @id123: OK")

    # 3.2 Тест @mention со скобками имени от ВК
    msg_vk_at = MagicMock()
    msg_vk_at.text = "+ban @id123456789 (Тестовый Пользователь) Нарушение правил"
    msg_vk_at.reply_message = None
    msg_vk_at.fwd_messages = []

    target, args = await resolve_target_and_args(msg_vk_at, mock_api, command_name="ban")
    assert target == 123456789, f"Target должен быть 123456789, получено {target}"
    assert args == "Нарушение правил", f"Args должен быть 'Нарушение правил', получено '{args}'"
    print("✅ Тег @id... (Имя Фамилия) со скобками: OK")

    # 3.3 Тест -ban по ID
    msg_unban = MagicMock()
    msg_unban.text = "-ban 123456789"
    msg_unban.reply_message = None
    msg_unban.fwd_messages = []

    target, args = await resolve_target_and_args(msg_unban, mock_api, command_name="unban")
    assert target == 123456789, f"Target должен быть 123456789, получено {target}"
    assert args == "", f"Args должен быть пустым, получено '{args}'"
    print("✅ Команда -ban с числовым ID: OK")


    # 4. Тест склонения русских слов
    forms = ("предупреждение", "предупреждения", "предупреждений")
    assert plural_ru(1, forms) == "предупреждение"
    assert plural_ru(2, forms) == "предупреждения"
    assert plural_ru(3, forms) == "предупреждения"
    assert plural_ru(5, forms) == "предупреждений"
    assert plural_ru(11, forms) == "предупреждений"
    assert plural_ru(21, forms) == "предупреждение"
    print("✅ Склонение числительных (plural_ru): OK")

    # 5. Тест форматирования длительности времени
    assert format_duration(15) == "15 минут"
    assert format_duration(60) == "1 час"
    assert format_duration(90) == "1 час 30 минут"
    print("✅ Форматирование длительности (format_duration): OK")

    print("\n🎉 Все тесты резолвера и форматтеров успешно пройдены!")


if __name__ == "__main__":
    asyncio.run(run_resolver_tests())
