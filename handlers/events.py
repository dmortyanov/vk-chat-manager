import os
import json
import logging
from vkbottle.bot import BotLabeler, Message, MessageEvent
from vkbottle import Keyboard, KeyboardButtonColor, Callback, GroupEventType, PhotoMessageUploader
from vkbottle.dispatch.rules.base import ChatActionRule
from config import Role, INSTRUCTION_PHOTO_PATH, INSTRUCTION_PHOTO_ATTACHMENT
from database.repository import Repository
from utils.formatters import get_user_mention
from utils.permissions import check_user_role

logger = logging.getLogger(__name__)
labeler = BotLabeler()


_cached_instruction_attachment: str | None = None


async def get_or_upload_instruction_photo(api) -> str | None:
    """
    Получает или загружает фото-инструкцию на сервера ВКонтакте от имени бота.
    Результат кэшируется в оперативной памяти на время работы процесса.
    """
    global _cached_instruction_attachment
    if _cached_instruction_attachment:
        return _cached_instruction_attachment

    # 1. Если в .env явно указан attachment сообщества (начинается с 'photo-')
    if INSTRUCTION_PHOTO_ATTACHMENT and INSTRUCTION_PHOTO_ATTACHMENT.startswith("photo-"):
        _cached_instruction_attachment = INSTRUCTION_PHOTO_ATTACHMENT
        return _cached_instruction_attachment

    # 2. Загружаем локальный файл instruction.png через PhotoMessageUploader
    if INSTRUCTION_PHOTO_PATH and os.path.isfile(INSTRUCTION_PHOTO_PATH):
        try:
            uploader = PhotoMessageUploader(api)
            # Загружаем без привязки к конкретному peer_id, чтобы attachment подходил для всех бесед
            att = await uploader.upload(INSTRUCTION_PHOTO_PATH)
            if att:
                _cached_instruction_attachment = att
                logger.info(f"Фото-инструкция успешно загружена в ВК и закэширована: {att}")
                return att
        except Exception as e:
            logger.error(f"Не удалось загрузить фото-инструкцию из файла {INSTRUCTION_PHOTO_PATH}: {e}")

    # 3. Fallback: если ничего другого нет, пробуем INSTRUCTION_PHOTO_ATTACHMENT
    if INSTRUCTION_PHOTO_ATTACHMENT:
        return INSTRUCTION_PHOTO_ATTACHMENT

    return None


async def send_bot_welcome_instruction(message: Message):
    """Отправляет фото-инструкцию и памятку при добавлении бота в беседу или по /инструкция"""
    global _cached_instruction_attachment
    attachment = await get_or_upload_instruction_photo(message.ctx_api)

    text = (
        "🤖 Спасибо за добавление чат-менеджера в беседу!\n\n"
        "📋 ПАМЯТКА ПО БЫСТРОЙ НАСТРОЙКЕ:\n"
        "1️⃣ Назначьте бота Администратором беседы (иначе бот не сможет удалять сообщения и модерировать).\n"
        "2️⃣ Главный администратор беседы должен ввести команду:\n"
        "   👉 /start\n"
        "   (это зафиксирует статус Спец администратора).\n"
        "3️⃣ Введите /команды для просмотра списка всех возможностей.\n"
        "4️⃣ Нажмите кнопку ниже для быстрой настройки фильтрации и запретов чата."
    )

    send_kwargs = {
        "peer_id": message.peer_id,
        "message": text,
        "random_id": 0
    }

    # Кнопку быстрых настроек запретов прикрепляем только для бесед (peer_id >= 2000000000)
    if message.peer_id >= 2000000000:
        send_kwargs["keyboard"] = (
            Keyboard(inline=True)
            .add(
                Callback("Настроить запреты", payload=json.dumps({"cmd": "sec_cats"})),
                color=KeyboardButtonColor.SECONDARY
            )
        ).get_json()

    if attachment:
        send_kwargs["attachment"] = attachment

    try:
        await message.ctx_api.messages.send(**send_kwargs)
    except Exception as e:
        logger.warning(f"Ошибка отправки инструкции с вложением {attachment}: {e}. Пробуем отправить без вложения...")
        # Если вложение вызвало отказ (например, неверный ID), сбрасываем кэш
        _cached_instruction_attachment = None
        send_kwargs.pop("attachment", None)
        try:
            await message.ctx_api.messages.send(**send_kwargs)
        except Exception as e2:
            logger.warning(f"Ошибка отправки с клавиатурой: {e2}. Пробуем отправить только текст...")
            send_kwargs.pop("keyboard", None)
            try:
                await message.ctx_api.messages.send(**send_kwargs)
            except Exception as e3:
                logger.error(f"Не удалось отправить инструкцию: {e3}")


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

    # Проверяем, не добавлен ли сам бот (сообщество)
    if user_id < 0:
        try:
            group_info = await message.ctx_api.groups.get_by_id()
            bot_group_id = group_info.groups[0].id if group_info.groups else 0
            if abs(user_id) == bot_group_id:
                await send_bot_welcome_instruction(message)
        except Exception as e:
            logger.warning(f"Ошибка проверки добавления сообщества: {e}")
        return

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


@labeler.chat_message(ChatActionRule(["chat_kick_user"]))
async def handle_user_leave(message: Message):
    """
    Обработка выхода / исключения участника из беседы.
    При добровольном выходе отправляет сообщение с кнопками [Кикнуть] и [Очистить].
    """
    action = message.action
    if not action:
        return

    kicked_user_id = action.member_id
    if kicked_user_id <= 0:
        return

    target_mention = await get_user_mention(kicked_user_id, message.ctx_api)

    # Инлайн-кнопки строго как на скриншоте ТЗ: Красная [Кикнуть] и Зеленая [Очистить]
    kb = (
        Keyboard(inline=True)
        .add(
            Callback("Кикнуть", payload=json.dumps({"cmd": "leave_kick", "uid": kicked_user_id, "cleaned": 0})),
            color=KeyboardButtonColor.NEGATIVE
        )
        .add(
            Callback("Очистить", payload=json.dumps({"cmd": "leave_clean", "uid": kicked_user_id, "kicked": 0})),
            color=KeyboardButtonColor.POSITIVE
        )
    ).get_json()

    await message.answer(f"🚪 Пользователь {target_mention} покинул беседу.", keyboard=kb)
