import aiosqlite
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from config import DATABASE_PATH

logger = logging.getLogger(__name__)


@asynccontextmanager
async def get_db() -> AsyncGenerator[aiosqlite.Connection, None]:
    """Асинхронный контекстный менеджер подключения к SQLite"""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA foreign_keys=ON")
        yield db


async def init_db():
    """Создает необходимые таблицы базы данных при первом запуске"""
    async with get_db() as db:
        await db.executescript("""
        CREATE TABLE IF NOT EXISTS chats (
            peer_id INTEGER PRIMARY KEY,
            owner_id INTEGER,
            silence_mode INTEGER DEFAULT 0,
            welcome_text TEXT,
            welcome_enabled INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS chat_members (
            peer_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            role INTEGER DEFAULT 0,
            messages_count INTEGER DEFAULT 0,
            warns_count INTEGER DEFAULT 0,
            mute_until INTEGER DEFAULT NULL,
            first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (peer_id, user_id)
        );

        CREATE TABLE IF NOT EXISTS chat_warns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            peer_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            admin_id INTEGER NOT NULL,
            reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS chat_bans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            peer_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            admin_id INTEGER NOT NULL,
            reason TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(peer_id, user_id)
        );

        CREATE INDEX IF NOT EXISTS idx_members_role ON chat_members(peer_id, role);
        CREATE INDEX IF NOT EXISTS idx_warns_chat ON chat_warns(peer_id, user_id);
        CREATE INDEX IF NOT EXISTS idx_bans_chat ON chat_bans(peer_id, user_id);
        """)
        await db.commit()
    logger.info("База данных SQLite успешно инициализирована.")
