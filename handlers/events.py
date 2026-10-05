import os
import json
import logging
from vkbottle.bot import BotLabeler, Message, MessageEvent
from vkbottle import Keyboard, KeyboardButtonColor, Callback, OpenLink, GroupEventType, PhotoMessageUploader
from vkbottle.dispatch.rules.base import ChatActionRule
from config import Role, INSTRUCTION_PHOTO_PATH, INSTRUCTION_PHOTO_URL, INSTRUCTION_PHOTO_ATTACHMENT
from database.repository import Repository
from utils.formatters import get_user_mention
from utils.permissions import check_user_role

logger = logging.getLogger(__name__)
labeler = BotLabeler()


_peer_photo_cache: dict[int, str] = {}
_cached_photo_bytes: bytes | None = None


async def get_instruction_photo_data() -> bytes | None:
    """Получает байты фото-инструкции по ссылке из интернета или из локального файла"""
    global _cached_photo_bytes
    if _cached_photo_bytes:
        return _cached_photo_bytes

    # 1. Если задан прямой URL на картинку
    target_url = INSTRUCTION_PHOTO_URL or (INSTRUCTION_PHOTO_PATH if str(INSTRUCTION_PHOTO_PATH).startswith("http") else "")
    if target_url:
        try:
            import aiohttp
            import re
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            connector = aiohttp.TCPConnector(ssl=False)
            async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
                # Если передана страница ibb.co (например, https://ibb.co/xtG49rZT), извлекаем прямую ссылку
                if "ibb.co/" in target_url and not any(target_url.lower().endswith(ext) for ext in (".png", ".jpg", ".jpeg", ".webp")):
                    try:
                        async with session.get(target_url, timeout=aiohttp.ClientTimeout(total=10)) as page_resp:
                            if page_resp.status == 200:
                                html = await page_resp.text()
                                m = re.search(r'property=["\']og:image["\'] content=["\']([^"\']+)["\']', html)
                                if not m:
                                    m = re.search(r'link rel=["\']image_src["\'] href=["\']([^"\']+)["\']', html)
                                if m:
                                    logger.info(f"Извлечена прямая ссылка из ibb.co: {m.group(1)}")
                                    target_url = m.group(1)
                    except Exception as e_parse:
                        logger.warning(f"Не удалось распарсить страницу {target_url}: {e_parse}")

                async with session.get(target_url, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status == 200:
                        _cached_photo_bytes = await resp.read()
                        logger.info(f"Фото-инструкция успешно скачана ({len(_cached_photo_bytes)} байт)")
                        return _cached_photo_bytes
                    else:
                        logger.error(f"Не удалось скачать фото-инструкцию по URL {target_url}: HTTP {resp.status}")
        except Exception as e:
            logger.error(f"Ошибка при скачивании фото-инструкции по URL {target_url}: {e}")

    # 2. Если есть локальный файл
    if INSTRUCTION_PHOTO_PATH and not str(INSTRUCTION_PHOTO_PATH).startswith("http") and os.path.isfile(INSTRUCTION_PHOTO_PATH):
        try:
            import aiofiles
            async with aiofiles.open(INSTRUCTION_PHOTO_PATH, "rb") as f:
                _cached_photo_bytes = await f.read()
                logger.info(f"Фото-инструкция прочитана из локального файла ({len(_cached_photo_bytes)} байт)")
                return _cached_photo_bytes
        except Exception as e:
            logger.error(f"Ошибка чтения локального файла {INSTRUCTION_PHOTO_PATH}: {e}")

    return None


async def get_photo_attachment_for_peer(api, peer_id: int) -> str | None:
    """
    Возвращает attachment для конкретного peer_id:
    1. Если в .env задан статический attachment сообщества (начинается с 'photo' и НЕ ссылка), возвращаем его.
    2. Если уже загружен для этого peer_id в кэше - возвращаем из кэша.
    3. Иначе скачиваем/читаем байты фото и загружаем через PhotoMessageUploader(api).upload(data, peer_id=peer_id).
    """
    # Если задан реальный VK attachment (photo-XXXX_YYYY или photoXXXX_YYYY), и это НЕ URL:
    if INSTRUCTION_PHOTO_ATTACHMENT and INSTRUCTION_PHOTO_ATTACHMENT.startswith("photo") and not INSTRUCTION_PHOTO_ATTACHMENT.startswith("http"):
        return INSTRUCTION_PHOTO_ATTACHMENT

    # Если фото уже загружено и привязано к этой беседе в кэше:
    if peer_id in _peer_photo_cache:
        return _peer_photo_cache[peer_id]

    # Скачиваем байты (по ссылке или из локального файла) и загружаем в ВК как НАСТОЯЩЕЕ ФОТО
    data = await get_instruction_photo_data()
    if data:
        try:
            uploader = PhotoMessageUploader(api)
            att = await uploader.upload(data, peer_id=peer_id)
            if att:
                _peer_photo_cache[peer_id] = att
                logger.info(f"Фото-инструкция успешно загружена в ВК для беседы {peer_id}: {att}")
                return att
        except Exception as e:
            logger.error(f"Не удалось загрузить фото-инструкцию в ВК для peer_id={peer_id}: {e}")

    return None


async def send_bot_welcome_instruction(message: Message):
    """Отправляет фото-инструкцию и памятку при добавлении бота в беседу или по /инструкция"""
    peer_id = message.peer_id
    attachment = await get_photo_attachment_for_peer(message.ctx_api, peer_id)

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
        "peer_id": peer_id,
        "message": text,
        "random_id": 0
    }

    # Кнопку быстрых настроек запретов прикрепляем только для бесед (peer_id >= 2000000000)
    if peer_id >= 2000000000:
        send_kwargs["keyboard"] = (
            Keyboard(inline=True)
            .add(
                Callback("Настроить запреты", payload=json.dumps({"cmd": "sec_cats"})),
                color=KeyboardButtonColor.SECONDARY
            )
        ).get_json()

    # Вложение должно быть ТОЛЬКО строкой photo... (настоящей фотографией), а не ссылкой
    if attachment and attachment.startswith("photo") and not attachment.startswith("http"):
        send_kwargs["attachment"] = attachment

    try:
        await message.ctx_api.messages.send(**send_kwargs)
        return
    except Exception as e:
        logger.warning(f"Ошибка отправки инструкции с вложением {attachment} в беседу {peer_id}: {e}")

    # Если отправка с текущим attachment завершилась ошибкой:
    # Принудительно пробуем загрузить байты заново
    data = await get_instruction_photo_data()
    if data:
        try:
            uploader = PhotoMessageUploader(message.ctx_api)
            fresh_att = await uploader.upload(data, peer_id=peer_id)
            if fresh_att and fresh_att != attachment:
                _peer_photo_cache[peer_id] = fresh_att
                send_kwargs["attachment"] = fresh_att
                await message.ctx_api.messages.send(**send_kwargs)
                logger.info(f"Инструкция успешно отправлена со свежезагруженным фото {fresh_att}")
                return
        except Exception as upload_err:
            logger.error(f"Повторная загрузка фото для peer_id={peer_id} не удалась: {upload_err}")

    # Fallback: если фото так и не удалось отправить, отправляем текст и клавиатуру
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
