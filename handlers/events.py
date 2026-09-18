import logging
from vkbottle.bot import BotLabeler, Message
from vkbottle.dispatch.rules.base import ChatActionRule
from database.repository import Repository
from utils.formatters import get_user_mention

logger = logging.getLogger(__name__)
labeler = BotLabeler()


@labeler.chat_message(ChatActionRule(["chat_invite_user", "chat_invite_user_by_link"]))
async def handle_chat_service_actions(message: Message):
    """
    Обработка сервисных сообщений беседы:
    - Вход нового участника по приглашению (chat_invite_user)
    - Вход нового участника по ссылке (chat_invite_user_by_link)
    """
    action = message.action
    if not action:
        return

    user_id = action.member_id or message.from_id
    if user_id <= 0:
        return  # Боты или группы

    peer_id = message.peer_id
    chat_id = peer_id - 2000000000

    # 1. Проверяем наличие в бан-листе беседы
    ban_info = await Repository.get_ban(peer_id, user_id)
    if ban_info:
        target_mention = await get_user_mention(user_id, message.ctx_api)
        try:
            await message.ctx_api.messages.remove_chat_user(chat_id=chat_id, member_id=user_id)
            await message.answer(
                f"🚫 Заблокированный пользователь {target_mention} попытался войти в беседу и был автоматически исключен.\n"
                f"📝 Причина блокировки: {ban_info['reason']}"
            )
            return
        except Exception as e:
            logger.error(f"Не удалось кикнуть забаненного пользователя {user_id}: {e}")

    # 2. Регистрируем участника в БД
    await Repository.get_or_create_member(peer_id, user_id)

    # 3. Отправляем приветственное сообщение (если настроено и включено)
    chat = await Repository.get_or_create_chat(peer_id)
    if chat.get("welcome_enabled", 1):
        welcome_text = chat.get("welcome_text")
        target_mention = await get_user_mention(user_id, message.ctx_api)

        chat_title = "беседу"
        try:
            conv_info = await message.ctx_api.messages.get_conversations_by_id(peer_ids=[peer_id])
            if conv_info.items and conv_info.items[0].chat_settings:
                chat_title = conv_info.items[0].chat_settings.title
        except Exception:
            pass

        if welcome_text:
            formatted_welcome = welcome_text.replace("{user}", target_mention).replace("{chat}", chat_title)
            await message.answer(formatted_welcome)
        else:
            await message.answer(f"👋 Приветствуем, {target_mention}, в беседе «{chat_title}»!")
