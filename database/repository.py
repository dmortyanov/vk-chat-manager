import time
from typing import Optional, List, Dict, Any
from config import Role
from database.db import get_db


class Repository:
    """Репозиторий для работы с беседами, участниками, варнами, мутами и банами"""

    # --- CHATS ---
    @staticmethod
    async def get_or_create_chat(peer_id: int, owner_id: Optional[int] = None) -> Dict[str, Any]:
        async with get_db() as db:
            async with db.execute("SELECT * FROM chats WHERE peer_id = ?", (peer_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    return dict(row)

            # Создаем новую беседу
            await db.execute(
                "INSERT INTO chats (peer_id, owner_id, silence_mode, welcome_enabled) VALUES (?, ?, 0, 1)",
                (peer_id, owner_id)
            )
            await db.commit()

            async with db.execute("SELECT * FROM chats WHERE peer_id = ?", (peer_id,)) as cursor:
                new_row = await cursor.fetchone()
                return dict(new_row)

    @staticmethod
    async def get_chat(peer_id: int) -> Optional[Dict[str, Any]]:
        async with get_db() as db:
            async with db.execute("SELECT * FROM chats WHERE peer_id = ?", (peer_id,)) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    @staticmethod
    async def get_all_chat_ids() -> List[int]:
        """Возвращает список всех зарегистрированных бесед бота (peer_id >= 2000000000)"""
        async with get_db() as db:
            async with db.execute("SELECT peer_id FROM chats WHERE peer_id >= 2000000000") as cursor:
                rows = await cursor.fetchall()
                return [row["peer_id"] for row in rows]

    @staticmethod
    async def get_owner_chats(owner_id: int) -> List[int]:
        """Возвращает список peer_id бесед, в которых пользователь является Спец администратором/владельцем"""
        async with get_db() as db:
            async with db.execute(
                """
                SELECT DISTINCT peer_id FROM (
                    SELECT peer_id FROM chats WHERE owner_id = ?
                    UNION
                    SELECT peer_id FROM chat_members WHERE user_id = ? AND role = ?
                ) WHERE peer_id >= 2000000000
                """,
                (owner_id, owner_id, Role.OWNER)
            ) as cursor:
                rows = await cursor.fetchall()
                return [row["peer_id"] for row in rows]

    @staticmethod
    async def set_chat_owner(peer_id: int, owner_id: int):
        async with get_db() as db:
            await db.execute(
                """
                INSERT INTO chats (peer_id, owner_id) VALUES (?, ?)
                ON CONFLICT(peer_id) DO UPDATE SET owner_id = excluded.owner_id
                """,
                (peer_id, owner_id)
            )
            # Также обновляем роль в chat_members
            await db.execute(
                """
                INSERT INTO chat_members (peer_id, user_id, role) VALUES (?, ?, ?)
                ON CONFLICT(peer_id, user_id) DO UPDATE SET role = ?
                """,
                (peer_id, owner_id, Role.OWNER, Role.OWNER)
            )
            await db.commit()

    @staticmethod
    async def set_silence(peer_id: int, enabled: bool):
        async with get_db() as db:
            val = 1 if enabled else 0
            await db.execute("UPDATE chats SET silence_mode = ? WHERE peer_id = ?", (val, peer_id))
            await db.commit()

    @staticmethod
    async def set_welcome(peer_id: int, text: Optional[str], enabled: bool = True):
        async with get_db() as db:
            val = 1 if enabled else 0
            await db.execute(
                "UPDATE chats SET welcome_text = ?, welcome_enabled = ? WHERE peer_id = ?",
                (text, val, peer_id)
            )
            await db.commit()

    # --- MEMBERS & ROLES ---
    @staticmethod
    async def get_or_create_member(peer_id: int, user_id: int) -> Dict[str, Any]:
        async with get_db() as db:
            async with db.execute(
                "SELECT * FROM chat_members WHERE peer_id = ? AND user_id = ?",
                (peer_id, user_id)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return dict(row)

            # Проверяем, не является ли пользователь владельцем беседы
            async with db.execute("SELECT owner_id FROM chats WHERE peer_id = ?", (peer_id,)) as cursor:
                chat_row = await cursor.fetchone()
                initial_role = Role.OWNER if (chat_row and chat_row["owner_id"] == user_id) else Role.USER

            await db.execute(
                "INSERT INTO chat_members (peer_id, user_id, role) VALUES (?, ?, ?)",
                (peer_id, user_id, initial_role)
            )
            await db.commit()

            async with db.execute(
                "SELECT * FROM chat_members WHERE peer_id = ? AND user_id = ?",
                (peer_id, user_id)
            ) as cursor:
                return dict(await cursor.fetchone())

    @staticmethod
    async def get_member_role(peer_id: int, user_id: int) -> int:
        member = await Repository.get_or_create_member(peer_id, user_id)
        return member["role"]

    @staticmethod
    async def set_member_role(peer_id: int, user_id: int, role: int):
        async with get_db() as db:
            await db.execute(
                """
                INSERT INTO chat_members (peer_id, user_id, role) VALUES (?, ?, ?)
                ON CONFLICT(peer_id, user_id) DO UPDATE SET role = ?
                """,
                (peer_id, user_id, role, role)
            )
            await db.commit()

    @staticmethod
    async def increment_messages(peer_id: int, user_id: int):
        async with get_db() as db:
            await db.execute(
                """
                INSERT INTO chat_members (peer_id, user_id, messages_count)
                VALUES (?, ?, 1)
                ON CONFLICT(peer_id, user_id) DO UPDATE SET messages_count = messages_count + 1
                """,
                (peer_id, user_id)
            )
            await db.commit()

    @staticmethod
    async def get_all_members_with_role(peer_id: int) -> List[Dict[str, Any]]:
        async with get_db() as db:
            async with db.execute(
                "SELECT * FROM chat_members WHERE peer_id = ? AND role > 0 ORDER BY role DESC",
                (peer_id,)
            ) as cursor:
                return [dict(row) for row in await cursor.fetchall()]

    @staticmethod
    async def get_members_by_role(peer_id: int, role: int) -> List[int]:
        """Возвращает список user_id участников с заданной ролью в беседе"""
        async with get_db() as db:
            async with db.execute(
                "SELECT user_id FROM chat_members WHERE peer_id = ? AND role = ? ORDER BY user_id ASC",
                (peer_id, role)
            ) as cursor:
                rows = await cursor.fetchall()
                return [row["user_id"] for row in rows]

    @staticmethod
    async def get_member_stats(peer_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        member = await Repository.get_or_create_member(peer_id, user_id)
        async with get_db() as db:
            async with db.execute(
                "SELECT COUNT(*) as total_warns FROM chat_warns WHERE peer_id = ? AND user_id = ?",
                (peer_id, user_id)
            ) as cursor:
                warn_row = await cursor.fetchone()
                member["history_warns_count"] = warn_row["total_warns"] if warn_row else 0
        return member

    # --- WARNS ---
    @staticmethod
    async def add_warn(peer_id: int, user_id: int, admin_id: int, reason: str = "Без причины") -> int:
        async with get_db() as db:
            # Заносим в историю
            await db.execute(
                "INSERT INTO chat_warns (peer_id, user_id, admin_id, reason) VALUES (?, ?, ?, ?)",
                (peer_id, user_id, admin_id, reason)
            )
            # Обновляем счетчик
            await db.execute(
                """
                INSERT INTO chat_members (peer_id, user_id, warns_count) VALUES (?, ?, 1)
                ON CONFLICT(peer_id, user_id) DO UPDATE SET warns_count = warns_count + 1
                """,
                (peer_id, user_id)
            )
            await db.commit()

            async with db.execute(
                "SELECT warns_count FROM chat_members WHERE peer_id = ? AND user_id = ?",
                (peer_id, user_id)
            ) as cursor:
                row = await cursor.fetchone()
                return row["warns_count"] if row else 1

    @staticmethod
    async def remove_warn(peer_id: int, user_id: int) -> int:
        async with get_db() as db:
            async with db.execute(
                "SELECT warns_count FROM chat_members WHERE peer_id = ? AND user_id = ?",
                (peer_id, user_id)
            ) as cursor:
                row = await cursor.fetchone()
                current = row["warns_count"] if row else 0

            new_count = max(0, current - 1)
            await db.execute(
                "UPDATE chat_members SET warns_count = ? WHERE peer_id = ? AND user_id = ?",
                (new_count, peer_id, user_id)
            )
            await db.commit()
            return new_count

    @staticmethod
    async def reset_warns(peer_id: int, user_id: int):
        async with get_db() as db:
            await db.execute(
                "UPDATE chat_members SET warns_count = 0 WHERE peer_id = ? AND user_id = ?",
                (peer_id, user_id)
            )
            await db.commit()

    @staticmethod
    async def get_user_warns(peer_id: int, user_id: int) -> List[Dict[str, Any]]:
        async with get_db() as db:
            async with db.execute(
                "SELECT * FROM chat_warns WHERE peer_id = ? AND user_id = ? ORDER BY id DESC LIMIT 10",
                (peer_id, user_id)
            ) as cursor:
                return [dict(row) for row in await cursor.fetchall()]

    @staticmethod
    async def get_chat_warned_users(peer_id: int) -> List[Dict[str, Any]]:
        async with get_db() as db:
            async with db.execute(
                "SELECT user_id, warns_count FROM chat_members WHERE peer_id = ? AND warns_count > 0 ORDER BY warns_count DESC",
                (peer_id,)
            ) as cursor:
                return [dict(row) for row in await cursor.fetchall()]

    # --- MUTES ---
    @staticmethod
    async def set_mute(peer_id: int, user_id: int, until_timestamp: int):
        async with get_db() as db:
            await db.execute(
                """
                INSERT INTO chat_members (peer_id, user_id, mute_until) VALUES (?, ?, ?)
                ON CONFLICT(peer_id, user_id) DO UPDATE SET mute_until = ?
                """,
                (peer_id, user_id, until_timestamp, until_timestamp)
            )
            await db.commit()

    @staticmethod
    async def remove_mute(peer_id: int, user_id: int):
        async with get_db() as db:
            await db.execute(
                "UPDATE chat_members SET mute_until = NULL WHERE peer_id = ? AND user_id = ?",
                (peer_id, user_id)
            )
            await db.commit()

    @staticmethod
    async def is_muted(peer_id: int, user_id: int) -> bool:
        async with get_db() as db:
            async with db.execute(
                "SELECT mute_until FROM chat_members WHERE peer_id = ? AND user_id = ?",
                (peer_id, user_id)
            ) as cursor:
                row = await cursor.fetchone()
                if not row or not row["mute_until"]:
                    return False
                now = int(time.time())
                if row["mute_until"] > now:
                    return True
                # Если мут истёк, сбрасываем
                await db.execute(
                    "UPDATE chat_members SET mute_until = NULL WHERE peer_id = ? AND user_id = ?",
                    (peer_id, user_id)
                )
                await db.commit()
                return False

    # --- BANS ---
    @staticmethod
    async def add_ban(peer_id: int, user_id: int, admin_id: int, reason: str = "Нарушение правил беседы"):
        async with get_db() as db:
            await db.execute(
                """
                INSERT INTO chat_bans (peer_id, user_id, admin_id, reason)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(peer_id, user_id) DO UPDATE SET
                    admin_id = excluded.admin_id,
                    reason = excluded.reason,
                    created_at = CURRENT_TIMESTAMP
                """,
                (peer_id, user_id, admin_id, reason)
            )
            # При бане сбрасываем роль на 0
            await db.execute(
                "UPDATE chat_members SET role = 0 WHERE peer_id = ? AND user_id = ?",
                (peer_id, user_id)
            )
            await db.commit()

    @staticmethod
    async def remove_ban(peer_id: int, user_id: int) -> bool:
        async with get_db() as db:
            async with db.execute(
                "DELETE FROM chat_bans WHERE peer_id = ? AND user_id = ?",
                (peer_id, user_id)
            ) as cursor:
                await db.commit()
                return cursor.rowcount > 0

    @staticmethod
    async def get_ban(peer_id: int, user_id: int) -> Optional[Dict[str, Any]]:
        async with get_db() as db:
            async with db.execute(
                "SELECT * FROM chat_bans WHERE peer_id = ? AND user_id = ?",
                (peer_id, user_id)
            ) as cursor:
                row = await cursor.fetchone()
                return dict(row) if row else None

    @staticmethod
    async def get_banlist(peer_id: int) -> List[Dict[str, Any]]:
        async with get_db() as db:
            async with db.execute(
                "SELECT * FROM chat_bans WHERE peer_id = ? ORDER BY id DESC LIMIT 50",
                (peer_id,)
            ) as cursor:
                return [dict(row) for row in await cursor.fetchall()]

    # --- RULES & SECURITY ---
    @staticmethod
    async def get_chat_rules(peer_id: int) -> Dict[str, str]:
        """Возвращает словарь настроенных правил для беседы: {rule_name: action}"""
        async with get_db() as db:
            async with db.execute(
                "SELECT rule_name, action FROM chat_rules WHERE peer_id = ?",
                (peer_id,)
            ) as cursor:
                rows = await cursor.fetchall()
                return {row["rule_name"]: row["action"] for row in rows}

    @staticmethod
    async def set_chat_rule(peer_id: int, rule_name: str, action: str):
        """Устанавливает действие для правила (разрешено, пред, мут, кик, бан)"""
        async with get_db() as db:
            await db.execute(
                """
                INSERT INTO chat_rules (peer_id, rule_name, action) VALUES (?, ?, ?)
                ON CONFLICT(peer_id, rule_name) DO UPDATE SET action = excluded.action
                """,
                (peer_id, rule_name, action)
            )
            await db.commit()

    # --- BANWORDS ---
    @staticmethod
    async def get_banwords(peer_id: int) -> List[str]:
        async with get_db() as db:
            async with db.execute(
                "SELECT word FROM chat_banwords WHERE peer_id = ? ORDER BY word ASC",
                (peer_id,)
            ) as cursor:
                rows = await cursor.fetchall()
                return [row["word"] for row in rows]

    @staticmethod
    async def add_banword(peer_id: int, word: str) -> bool:
        word = word.strip().lower()
        if not word:
            return False
        async with get_db() as db:
            try:
                await db.execute(
                    "INSERT INTO chat_banwords (peer_id, word) VALUES (?, ?)",
                    (peer_id, word)
                )
                await db.commit()
                return True
            except Exception:
                return False

    @staticmethod
    async def remove_banword(peer_id: int, word: str) -> bool:
        word = word.strip().lower()
        async with get_db() as db:
            async with db.execute(
                "DELETE FROM chat_banwords WHERE peer_id = ? AND word = ?",
                (peer_id, word)
            ) as cursor:
                await db.commit()
                return cursor.rowcount > 0

    # --- RECENT MESSAGES (FOR PURGE / CLEANUP) ---
    @staticmethod
    async def save_message_cmid(peer_id: int, user_id: int, cmid: int):
        async with get_db() as db:
            await db.execute(
                "INSERT INTO chat_messages (peer_id, user_id, cmid) VALUES (?, ?, ?)",
                (peer_id, user_id, cmid)
            )
            # Очищаем очень старые сообщения (старше 2 дней) время от времени
            await db.execute(
                "DELETE FROM chat_messages WHERE created_at < datetime('now', '-2 days')"
            )
            await db.commit()

    @staticmethod
    async def get_user_cmids(peer_id: int, user_id: int, limit: int = 100) -> List[int]:
        """Возвращает conversation_message_id последних сообщений пользователя за 24 часа"""
        async with get_db() as db:
            async with db.execute(
                """
                SELECT cmid FROM chat_messages 
                WHERE peer_id = ? AND user_id = ? AND created_at >= datetime('now', '-1 day')
                ORDER BY id DESC LIMIT ?
                """,
                (peer_id, user_id, limit)
            ) as cursor:
                rows = await cursor.fetchall()
                return [row["cmid"] for row in rows]

    @staticmethod
    async def delete_user_cmids(peer_id: int, user_id: int):
        async with get_db() as db:
            await db.execute(
                "DELETE FROM chat_messages WHERE peer_id = ? AND user_id = ?",
                (peer_id, user_id)
            )
            await db.commit()
