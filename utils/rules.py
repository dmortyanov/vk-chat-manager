import re
from typing import List, Tuple
from vkbottle.dispatch.rules import ABCRule
from config import COMMAND_PREFIXES

BOT_MENTION_REGEX = re.compile(r"^(?:\[(?:club|public)\d+\|[^\]]+\]|@(?:club|public)\d+)\s*,?\s*", re.IGNORECASE)

# Допустимые символы начала команд (команды без этих префиксов не обрабатываются)
VALID_COMMAND_STARTS = ("/", "+", "-")


class CommandRule(ABCRule):
    """
    Строгое правило для команд чат-менеджера:
    - Все команды ОБЯЗАТЕЛЬНО должны начинаться с '/' или '+' (или '-')
    - Обычные текстовые слова (например, "бот", "тут", "стата") полностью игнорируются
    - Автоматически отсекает упоминание сообщества/бота в начале сообщения ([club123|Бот] /start -> /start)
    - Не чувствительно к регистру (/START == /start)
    - Корректно работает с аргументами (/kick @user) и составными командами ('/warnings in the chat')
    """

    def __init__(self, commands: List[str], prefixes: Tuple[str, ...] = COMMAND_PREFIXES):
        # Сортируем команды по длине от длинных к коротким, чтобы длинные фразы имели приоритет
        self.commands = sorted([c.lower().strip() for c in commands], key=len, reverse=True)
        self.prefixes = prefixes

    async def check(self, event) -> bool:
        text = (getattr(event, "text", "") or "").strip()
        if not text:
            return False

        # Очищаем от упоминания сообщества/бота в начале строки [club123|Имя] или @club123
        clean = BOT_MENTION_REGEX.sub("", text).strip().lower()
        if not clean:
            return False

        # Строгая проверка: сообщение ОБЯЗАТЕЛЬНО должно начинаться с допустимого префикса
        if not any(clean.startswith(start) for start in VALID_COMMAND_STARTS):
            return False

        for cmd in self.commands:
            for prefix in self.prefixes:
                full_cmd = f"{prefix}{cmd}".lower()
                if clean == full_cmd or clean.startswith(f"{full_cmd} "):
                    return True

        return False
