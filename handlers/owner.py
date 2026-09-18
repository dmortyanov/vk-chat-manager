import json
import asyncio
import logging
from vkbottle.bot import BotLabeler, Message, MessageEvent
from vkbottle import Keyboard, KeyboardButtonColor, Callback, GroupEventType
from config import Role, DEV_IDS
from database.repository import Repository
from utils.rules import CommandRule
from utils.resolver import resolve_target_and_args
from utils.formatters import get_user_mention
from utils.permissions import check_user_role, is_user_in_chat

logger = logging.getLogger(__name__)
labeler = BotLabeler()


@labeler.message(CommandRule(["start", "старт"]))
async def cmd_start(message: Message):
    """Инициализация беседы и назначение главного администратора"""
    if message.peer_id < 2000000000:
        return await message.reply("❌ Команда /start должна вызываться внутри беседы ВКонтакте!")

    peer_id = message.peer_id
    chat = await Repository.get_chat(peer_id)

    # Проверяем реального создателя беседы через VK API
    vk_owner_id = message.from_id
    try:
        conv_info = await message.ctx_api.messages.get_conversations_by_id(peer_ids=[peer_id])
        if conv_info.items and conv_info.items[0].chat_settings:
            vk_owner_id = conv_info.items[0].chat_settings.owner_id
    except Exception as e:
        logger.warning(f"Не удалось получить создателя беседы через API: {e}")

    # Если беседа еще не была зарегистрирована или вызывающий — создатель беседы
    if not chat or not chat.get("owner_id") or message.from_id == vk_owner_id:
        await Repository.set_chat_owner(peer_id, message.from_id)
        owner_mention = await get_user_mention(message.from_id, message.ctx_api)

        return await message.answer(
            f"🎉 Беседа успешно инициализирована!\n\n"
            f"👑 Главный администратор: {owner_mention}\n"
            f"🛡️ Чат-менеджер готов к работе.\n\n"
            f"💡 Введите /команды, чтобы ознакомиться со всеми возможностями бота.\n"
            f"⚙️ Не забудьте выдать боту права Администратора в настройках беседы!"
        )

    owner_mention = await get_user_mention(chat["owner_id"], message.ctx_api)
    await message.reply(
        f"ℹ️ Эта беседа уже инициализирована.\n"
        f"👑 Главный администратор беседы: {owner_mention}"
    )


@labeler.message(CommandRule(["+admin", "+админ"], prefixes=("", "/")))
async def cmd_promote_admin(message: Message):
    """Назначение администратора беседы (доступно Главному админу)"""
    if message.peer_id < 2000000000:
        return await message.reply("❌ Команда доступна только в беседах!")

    caller_role = await check_user_role(message.peer_id, message.from_id)
    if caller_role < Role.OWNER:
        return

    target_id, _ = await resolve_target_and_args(message, message.ctx_api, command_name="+admin")
    if not target_id:
        return await message.reply("❌ Укажите ID пользователя для назначения администратором (ответом на сообщение, ссылкой или @упоминанием).")

    if not await is_user_in_chat(message.peer_id, target_id, message.ctx_api):
        return await message.reply("❌ Данного пользователя нет в этой беседе!")

    if target_id == message.from_id:
        return await message.reply("❌ Вы уже являетесь Главным администратором!")

    await Repository.set_member_role(message.peer_id, target_id, Role.ADMIN)

    target_mention = await get_user_mention(target_id, message.ctx_api)
    owner_mention = await get_user_mention(message.from_id, message.ctx_api)

    await message.answer(
        f"⭐ Пользователь {target_mention} назначен Администратором беседы!\n"
        f"👑 Назначил: {owner_mention}"
    )


@labeler.message(CommandRule(["-admin", "-админ"], prefixes=("", "/")))
async def cmd_demote_admin(message: Message):
    """Снятие прав администратора (доступно Главному админу)"""
    if message.peer_id < 2000000000:
        return await message.reply("❌ Команда доступна только в беседах!")

    caller_role = await check_user_role(message.peer_id, message.from_id)
    if caller_role < Role.OWNER:
        return

    target_id, _ = await resolve_target_and_args(message, message.ctx_api, command_name="-admin")
    if not target_id:
        return await message.reply("❌ Укажите ID пользователя для снятия прав администратора (ответом, ссылкой или @упоминанием).")

    if not await is_user_in_chat(message.peer_id, target_id, message.ctx_api):
        return await message.reply("❌ Данного пользователя нет в этой беседе!")

    target_role = await check_user_role(message.peer_id, target_id)
    if target_role != Role.ADMIN:
        return await message.reply("❌ Данный пользователь не является администратором!")

    await Repository.set_member_role(message.peer_id, target_id, Role.USER)

    target_mention = await get_user_mention(target_id, message.ctx_api)
    owner_mention = await get_user_mention(message.from_id, message.ctx_api)

    await message.answer(
        f"👤 С пользователя {target_mention} сняты полномочия Администратора.\n"
        f"👑 Действие выполнил: {owner_mention}"
    )


@labeler.message(CommandRule(["приветствие", "welcome"], prefixes=("/",)))
async def cmd_welcome(message: Message):
    """Настройка приветственного сообщения для новых участников"""
    if message.peer_id < 2000000000:
        return await message.reply("❌ Команда доступна только в беседах!")

    caller_role = await check_user_role(message.peer_id, message.from_id)
    if caller_role < Role.OWNER:
        return

    _, text_arg = await resolve_target_and_args(message, message.ctx_api, command_name="приветствие")
    arg = text_arg.strip()

    chat = await Repository.get_or_create_chat(message.peer_id)

    if not arg or arg.lower() in ("показать", "show", "инфо"):
        cur_text = chat.get("welcome_text") or "По умолчанию (Добро пожаловать в беседу!)"
        status = "Включено ✅" if chat.get("welcome_enabled", 1) else "Выключено ❌"
        return await message.reply(
            f"👋 Настройки приветствия:\n"
            f"Статус: {status}\n\n"
            f"Текст приветствия:\n{cur_text}\n\n"
            f"💡 Доступные теги в тексте:\n"
            f"• {{user}} — кликабельное имя вступившего\n"
            f"• {{chat}} — название беседы\n\n"
            f"Команды:\n"
            f"• /приветствие [текст] — установить новый текст\n"
            f"• /приветствие выкл — отключить приветствие\n"
            f"• /приветствие вкл — включить приветствие"
        )

    if arg.lower() in ("выкл", "откл", "off", "disable"):
        await Repository.set_welcome(message.peer_id, chat.get("welcome_text"), enabled=False)
        return await message.reply("❌ Приветствие новых участников отключено.")

    if arg.lower() in ("вкл", "on", "enable"):
        await Repository.set_welcome(message.peer_id, chat.get("welcome_text"), enabled=True)
        return await message.reply("✅ Приветствие новых участников включено.")

    # Установка нового текста
    await Repository.set_welcome(message.peer_id, text=arg, enabled=True)
    await message.reply(
        f"✅ Новое приветствие успешно установлено!\n\n"
        f"Предпросмотр:\n{arg}\n\n"
        f"💡 Теги {{user}} и {{chat}} будут автоматически заменяться при входе нового участника."
    )


@labeler.message(CommandRule(["demote подтвердить", "расформировать подтвердить"]))
async def cmd_demote_confirm_text(message: Message):
    """Текстовое подтверждение расформирования беседы"""
    caller_role = await check_user_role(message.peer_id, message.from_id)
    if caller_role < Role.OWNER:
        return

    await execute_demote(message.peer_id, message.from_id, message.ctx_api)


@labeler.message(CommandRule(["demote", "расформировать"]))
async def cmd_demote(message: Message):
    """Инициализация процесса расформирования беседы с подтверждением"""
    if message.peer_id < 2000000000:
        return await message.reply("❌ Команда доступна только в беседах!")

    caller_role = await check_user_role(message.peer_id, message.from_id)
    if caller_role < Role.OWNER:
        return

    # Интерактивная инлайн-клавиатура с подтверждением
    kb = (
        Keyboard(inline=True)
        .add(
            Callback("✅ Да, расформировать", payload=json.dumps({"cmd": "confirm_demote", "owner_id": message.from_id})),
            color=KeyboardButtonColor.NEGATIVE
        )
        .add(
            Callback("❌ Отмена", payload=json.dumps({"cmd": "cancel_demote", "owner_id": message.from_id})),
            color=KeyboardButtonColor.SECONDARY
        )
    ).get_json()

    await message.answer(
        "⚠️ ВНИМАНИЕ! Вы собираетесь расформировать беседу!\n\n"
        "Бот исключит ВСЕХ обычных участников, не имеющих роли (модераторы и администраторы останутся).\n"
        "Это действие необратимо!\n\n"
        "Для подтверждения нажмите кнопку ниже или напишите: /demote подтвердить",
        keyboard=kb
    )


@labeler.raw_event(GroupEventType.MESSAGE_EVENT, dataclass=MessageEvent)
async def handle_demote_callback(event: MessageEvent):
    """Обработчик интерактивных кнопок VK для расформирования беседы"""
    payload = event.payload
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except Exception:
            return

    cmd = payload.get("cmd")
    if cmd not in ("confirm_demote", "cancel_demote"):
        return

    expected_owner = payload.get("owner_id")
    if event.user_id != expected_owner:
        return await event.show_snackbar("❌ Только инициатор (Главный админ) может нажать эту кнопку!")

    peer_id = event.peer_id

    if cmd == "cancel_demote":
        await event.ctx_api.messages.send(
            peer_id=peer_id,
            random_id=0,
            message="🛡️ Расформирование беседы отменено."
        )
        await event.show_snackbar("Действие отменено.")
        return

    if cmd == "confirm_demote":
        await event.show_snackbar("Начинаю расформирование беседы...")
        await execute_demote(peer_id, event.user_id, event.ctx_api)


async def execute_demote(peer_id: int, admin_id: int, api):
    """Выполняет исключение всех обычных участников беседы"""
    chat_id = peer_id - 2000000000
    try:
        members_resp = await api.messages.get_conversation_members(peer_id=peer_id)
        items = members_resp.items
    except Exception as e:
        await api.messages.send(
            peer_id=peer_id,
            random_id=0,
            message=f"❌ Ошибка получения участников беседы. Убедитесь, что у бота есть права администратора!\nОшибка: {e}"
        )
        return

    kicked_count = 0

    await api.messages.send(
        peer_id=peer_id,
        random_id=0,
        message="⏳ Расформирование началось... Исключаю пользователей без ролей."
    )

    for item in items:
        uid = item.member_id
        if uid <= 0:
            continue

        role = await Repository.get_member_role(peer_id, uid)
        # Исключаем только тех, у кого роль 0 (обычный участник)
        if role == Role.USER:
            try:
                await api.messages.remove_chat_user(chat_id=chat_id, member_id=uid)
                kicked_count += 1
            except Exception:
                pass

    admin_mention = await get_user_mention(admin_id, api)
    await api.messages.send(
        peer_id=peer_id,
        random_id=0,
        message=(
            f"🧹 Расформирование беседы завершено!\n\n"
            f"👑 Инициатор: {admin_mention}\n"
            f"🚪 Исключено обычных участников: {kicked_count}\n"
            f"🛡️ Модераторы и администраторы сохранены в беседе."
        )
    )


@labeler.message(CommandRule(["рассылка", "broadcast"], prefixes=("/",)))
async def cmd_broadcast(message: Message):
    """
    Глобальная рассылка сообщений по всем зарегистрированным беседам бота.
    Доступна исключительно разработчикам/создателям бота (DEV_IDS).
    """
    if message.from_id not in DEV_IDS:
        return

    # Извлекаем текст после команды
    text = (message.text or "").strip()
    parts = text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        return await message.reply(
            "❌ Укажите текст для рассылки!\n"
            "Пример: /рассылка Внимание! Вышло обновление 2.0. Добавлены новые команды."
        )

    broadcast_text = parts[1].strip()

    # Извлекаем вложения (фото, документы и т.д.), если они были прикреплены к сообщению
    attachment_str = None
    try:
        attachments = message.get_attachment_strings()
        if attachments:
            attachment_str = ",".join(attachments)
    except Exception:
        attachment_str = None

    chat_ids = await Repository.get_all_chat_ids()
    if not chat_ids:
        return await message.reply("❌ В базе данных пока нет зарегистрированных бесед для рассылки.")

    await message.reply(f"⏳ Начинаю рассылку обновления... Найдено бесед: {len(chat_ids)}")

    success_count = 0
    fail_count = 0

    for peer_id in chat_ids:
        try:
            send_kwargs = {
                "peer_id": peer_id,
                "message": broadcast_text,
                "random_id": 0,
            }
            if attachment_str:
                send_kwargs["attachment"] = attachment_str

            await message.ctx_api.messages.send(**send_kwargs)
            success_count += 1
        except Exception as e:
            fail_count += 1
            logger.warning(f"Не удалось доставить рассылку в беседу {peer_id}: {e}")

        # Безопасная пауза 0.1с между сообщениями (не превышает 10 запросов в секунду)
        await asyncio.sleep(0.1)

    author_mention = await get_user_mention(message.from_id, message.ctx_api)
    await message.reply(
        f"📢 Рассылка обновления успешно завершена!\n\n"
        f"👤 Инициатор: {author_mention}\n"
        f"✅ Доставлено в бесед: {success_count}\n"
        f"⚠️ Ошибок отправки: {fail_count}\n"
        f"💬 Всего бесед в базе: {len(chat_ids)}"
    )

