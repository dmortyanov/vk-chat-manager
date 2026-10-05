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

INSTRUCTION_PHOTO_URL = os.getenv("INSTRUCTION_PHOTO_URL", "").strip()

raw_photo_path = os.getenv("INSTRUCTION_PHOTO_PATH", "assets/instruction.png").strip()
if raw_photo_path.startswith("http://") or raw_photo_path.startswith("https://"):
    if not INSTRUCTION_PHOTO_URL:
        INSTRUCTION_PHOTO_URL = raw_photo_path
    INSTRUCTION_PHOTO_PATH = raw_photo_path
else:
    _p = Path(raw_photo_path)
    if not _p.is_absolute():
        _p = (BASE_DIR / _p).resolve()
    INSTRUCTION_PHOTO_PATH = str(_p)

INSTRUCTION_PHOTO_ATTACHMENT = os.getenv("INSTRUCTION_PHOTO_ATTACHMENT", "").strip()


class Role(IntEnum):
    """Иерархия ролей в чат-менеджере"""
    USER = 0        # Обычный участник беседы
    MODERATOR = 1   # Модератор (1 уровень)
    ADMIN = 2       # Администратор (2 уровень)
    OWNER = 3       # Спец администратор / Создатель беседы (3 уровень)

    @classmethod
    def title(cls, role_val: int) -> str:
        titles = {
            cls.USER: "👤 Участник",
            cls.MODERATOR: "🛡️ Модератор",
            cls.ADMIN: "⭐ Администратор",
            cls.OWNER: "👑 Спец администратор",
        }
        return titles.get(role_val, "👤 Участник")
