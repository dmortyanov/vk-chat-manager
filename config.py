import os
import re
from enum import IntEnum
from pathlib import Path
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

VK_TOKEN = os.getenv("VK_TOKEN", "")
DATABASE_PATH = os.getenv("DATABASE_PATH", str(BASE_DIR / "chat_manager.db"))

raw_prefixes = os.getenv("COMMAND_PREFIXES", "/")
COMMAND_PREFIXES = tuple(p.strip() for p in raw_prefixes.split(",") if p.strip()) or ("/",)

raw_dev_ids = os.getenv("DEV_IDS", "")
DEV_IDS = tuple(int(x) for x in re.findall(r"\d+", raw_dev_ids))


class Role(IntEnum):
    """Иерархия ролей в чат-менеджере"""
    USER = 0        # Обычный участник беседы
    MODERATOR = 1   # Модератор (1 уровень)
    ADMIN = 2       # Администратор (2 уровень)
    OWNER = 3       # Главный администратор / Создатель беседы (3 уровень)

    @classmethod
    def title(cls, role_val: int) -> str:
        titles = {
            cls.USER: "👤 Участник",
            cls.MODERATOR: "🛡️ Модератор",
            cls.ADMIN: "⭐ Администратор",
            cls.OWNER: "👑 Главный администратор",
        }
        return titles.get(role_val, "👤 Участник")
