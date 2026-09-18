import logging
from vkbottle import BaseMiddleware
from vkbottle.bot import Message
from config import Role
from database.repository import Repository

logger = logging.getLogger(__name__)


class ModerationMiddleware(BaseMiddleware[Message]):
    """
    Middleware для:
    1. Учета статистики сообщений участников (/stata)
    2. Проверки активного мута (/mute) и удаления сообщений нарушителя
    3. Проверки режима тишины (/Тишина) и удаления сообщений обычных пользователей
    """

    async def pre(self):
        message = self.event

        # Проверяем, что событие происходит в групповой беседе (peer_id > 2000000000)
        if message.peer_id < 2000000000:
            return

        user_id = message.from_id
        peer_id = message.peer_id

        # Если сообщение от сообщества (отрицательный ID)
        if user_id <= 0:
            return

        # 1. Учитываем статистику сообщений
        try:
            await Repository.increment_messages(peer_id, user_id)
        except Exception as e:
            logger.error(f"Ошибка учета сообщения пользователя {user_id}: {e}")

        # 2. Проверяем активный мут пользователя
        try:
            if await Repository.is_muted(peer_id, user_id):
                # Удаляем сообщение для всех
                await message.ctx_api.messages.delete(
                    cmids=[message.conversation_message_id],
                    peer_id=peer_id,
                    delete_for_all=True
                )
                self.stop("Пользователь заглушен")
                return
        except Exception as e:
            logger.warning(f"Не удалось удалить сообщение заглушенного пользователя {user_id}: {e}")

        # 3. Проверяем режим тишины в беседе
        try:
            chat = await Repository.get_chat(peer_id)
            if chat and chat.get("silence_mode") == 1:
                role = await Repository.get_member_role(peer_id, user_id)
                # Если обычный участник (роль 0) — удаляем сообщение
                if role < Role.MODERATOR:
                    await message.ctx_api.messages.delete(
                        cmids=[message.conversation_message_id],
                        peer_id=peer_id,
                        delete_for_all=True
                    )
                    self.stop("Режим тишины включен")
                    return
        except Exception as e:
            logger.warning(f"Ошибка проверки режима тишины в чате {peer_id}: {e}")
