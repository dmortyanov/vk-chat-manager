import re
from typing import Optional, Tuple
from vkbottle.bot import Message
from vkbottle import ABCAPI

# Регулярные выражения
MENTION_START_REGEX = re.compile(r"^\[(?:id|club)(\d+)\|[^\]]+\]", re.IGNORECASE)
VK_LINK_START_REGEX = re.compile(r"^(?:https?:\/\/)?(?:m\.)?vk\.com\/([a-zA-Z0-9_\.]+)", re.IGNORECASE)
AT_MENTION_START_REGEX = re.compile(r"^[@*]([a-zA-Z0-9_\.]+)(?:\s*\([^)]+\))?", re.IGNORECASE)
NUMERIC_ID_REGEX = re.compile(r"^(?:id)?(\d+)$", re.IGNORECASE)

# Слова, которые не должны резолвиться как короткие имена профилей ВКонтакте
STOP_WORDS = {
    "in", "the", "chat", "беседа", "чат", "все", "all",
    "тут", "здесь", "варны", "варн", "кик", "мут", "бан", "разбан"
}


async def resolve_target_and_args(
    message: Message,
    api: ABCAPI,
    command_name: str = ""
) -> Tuple[Optional[int], str]:
    """
    Интеллектуальный определитель целевого пользователя.
    Ищет цель:
    1. По ответу на сообщение (reply_message)
    2. По пересланному сообщению (fwd_messages)
    3. По упоминанию в тексте ([id123|Имя Фамилия], @screen_name или @id123)
    4. По ссылке (vk.com/...)
    5. По прямому ID (id123, 123)

    Возвращает (target_id, remaining_args_text).
    """
    text = (message.text or "").strip()

    # Очищаем от упоминания сообщества/бота в начале строки
    text = re.sub(r"^(?:\[(?:club|public)\d+\|[^\]]+\]|@(?:club|public)\d+)\s*,?\s*", "", text, flags=re.IGNORECASE).strip()

    # Убираем команду из начала текста
    if command_name and " " in command_name:
        # Для составных команд ('number of warnings', 'warnings in the chat')
        for prefix in ("/", "+", "-", "!", ".", ""):
            cmd_variant = f"{prefix}{command_name}".strip().lower()
            if text.lower().startswith(cmd_variant):
                text = text[len(cmd_variant):].strip()
                break
    else:
        # Для одиночных команд: убираем первый токен, если он начинается с префикса или равен имени команды
        words = text.split(maxsplit=1)
        if words:
            first_word = words[0]
            if any(first_word.startswith(p) for p in ("/", "+", "-", "!", ".")) or (command_name and first_word.lower() == command_name.lower()):
                text = words[1].strip() if len(words) > 1 else ""

    # 1. Проверяем ответ на сообщение (reply)
    if message.reply_message and message.reply_message.from_id:
        target_id = message.reply_message.from_id
        return target_id, text

    # 2. Проверяем пересланные сообщения (forwarded)
    if message.fwd_messages and len(message.fwd_messages) > 0:
        target_id = message.fwd_messages[0].from_id
        return target_id, text

    if not text:
        return None, ""

    # 3. Проверяем VK упоминание: [id12345|Любой Текст с пробелами]
    mention_match = MENTION_START_REGEX.match(text)
    if mention_match:
        target_id = int(mention_match.group(1))
        remaining_text = text[mention_match.end():].lstrip(",:; ").strip()
        return target_id, remaining_text

    # 4. Проверяем ссылку на профиль: vk.com/...
    link_match = VK_LINK_START_REGEX.match(text)
    if link_match:
        screen_name = link_match.group(1)
        remaining_text = text[link_match.end():].lstrip(",:; ").strip()
        target_id = await _resolve_screen_name(screen_name, api)
        if target_id:
            return target_id, remaining_text

    # 5. Проверяем @mentions: @durov, @id12345, *durov, @id123 (Имя Фамилия)
    at_match = AT_MENTION_START_REGEX.match(text)
    if at_match:
        screen_name = at_match.group(1)
        remaining_text = text[at_match.end():].lstrip(",:; ").strip()
        target_id = await _resolve_screen_name(screen_name, api)
        if target_id:
            return target_id, remaining_text

    # 6. Проверяем формат id12345 или чисто числовой ID в первом слове
    words = text.split(maxsplit=1)
    first_arg = words[0]
    remaining_text = words[1].strip() if len(words) > 1 else ""

    num_match = NUMERIC_ID_REGEX.match(first_arg)
    if num_match:
        target_id = int(num_match.group(1))
        return target_id, remaining_text

    # 7. Возможно первый аргумент - короткое имя (domain без @ и vk.com)
    if first_arg.lower() not in STOP_WORDS:
        target_id = await _resolve_screen_name(first_arg, api)
        if target_id:
            return target_id, remaining_text

    return None, text


async def _resolve_screen_name(name: str, api: ABCAPI) -> Optional[int]:
    """Разрешает короткое имя пользователя (domain) в числовой ID через VK API"""
    clean_name = name.lower().strip("@/* ")
    if clean_name.startswith("id") and clean_name[2:].isdigit():
        return int(clean_name[2:])

    if clean_name.isdigit():
        return int(clean_name)

    if clean_name in STOP_WORDS:
        return None

    try:
        res = await api.utils.resolve_screen_name(screen_name=clean_name)
        if res and hasattr(res, "type") and res.type:
            val = res.type.value if hasattr(res.type, "value") else str(res.type)
            if val in ("user", "group"):
                return res.object_id if val == "user" else -res.object_id
    except Exception:
        pass
    return None
