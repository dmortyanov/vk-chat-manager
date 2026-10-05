from datetime import datetime, timezone, timedelta
from vkbottle.bot import BotLabeler, Message
from config import Role
from database.repository import Repository
from utils.rules import CommandRule
from utils.resolver import resolve_target_and_args
from utils.vk_date import get_vk_registration_date
from utils.formatters import get_user_mention, format_msk_datetime
from utils.permissions import is_user_in_chat

labeler = BotLabeler()
MSK_TZ = timezone(timedelta(hours=3))


@labeler.message(CommandRule(["тут", "ping"], prefixes=("/",)))
async def cmd_tut(message: Message):
    """Проверка работоспособности бота"""
    now = datetime.now(MSK_TZ).strftime("%d.%m.%Y в %H:%M:%S (МСК)")
    chat_id = message.peer_id - 2000000000 if message.peer_id > 2000000000 else message.peer_id
    await message.reply(
        f"🟢 Чат-менеджер на связи и готов к работе!\n"
        f"⚡ Система функционирует стабильно.\n"
        f"💬 Номер беседы: #{chat_id}\n"
        f"🕒 Время сервера: {now}"
    )


@labeler.message(CommandRule(["stata", "стата", "статистика"]))
async def cmd_stata(message: Message):
    """Просмотр статистики участника в беседе"""
    if message.peer_id < 2000000000:
        return await message.reply("❌ Данная команда предназначена только для бесед!")

    target_id, _ = await resolve_target_and_args(message, message.ctx_api, command_name="stata")
    if not target_id:
        target_id = message.from_id

    if not await is_user_in_chat(message.peer_id, target_id, message.ctx_api):
        return await message.reply("❌ Данного пользователя нет в этой беседе!")

    stats = await Repository.get_member_stats(message.peer_id, target_id)
    if not stats:
        return await message.reply("❌ Не удалось получить статистику пользователя.")

    role_title = Role.title(stats.get("role", 0))
    mention = await get_user_mention(target_id, message.ctx_api)

    first_seen = format_msk_datetime(stats.get("first_seen_at"))
    msgs = stats.get("messages_count", 0)
    warns = stats.get("warns_count", 0)
    history_warns = stats.get("history_warns_count", 0)

    # Проверяем мут
    mute_status = "Нет"
    if await Repository.is_muted(message.peer_id, target_id):
        mute_status = "🔴 Активен"

    text = (
        f"📊 Статистика участника {mention}:\n\n"
        f"👑 Статус: {role_title}\n"
        f"💬 Отправлено сообщений: {msgs}\n"
        f"⚠️ Активных предупреждений: {warns}/3\n"
        f"📜 Всего нарушений в истории: {history_warns}\n"
        f"🔇 Заглушка (мут): {mute_status}\n"
        f"📅 Впервые замечен: {first_seen}"
    )
    await message.reply(text)


@labeler.message(CommandRule(["reg", "рег", "регистрация"]))
async def cmd_reg(message: Message):
    """Определение даты регистрации пользователя ВКонтакте через FOAF / ID"""
    target_id, _ = await resolve_target_and_args(message, message.ctx_api, command_name="reg")
    if not target_id:
        target_id = message.from_id

    if message.peer_id >= 2000000000 and not await is_user_in_chat(message.peer_id, target_id, message.ctx_api):
        return await message.reply("❌ Данного пользователя нет в этой беседе!")

    if target_id <= 0:
        return await message.reply("❌ Нельзя посмотреть дату регистрации сообщества/бота.")

    mention = await get_user_mention(target_id, message.ctx_api)
    reg_date = await get_vk_registration_date(target_id)

    if not reg_date:
        return await message.reply(f"❌ Не удалось получить дату регистрации для {mention}. Возможно страница удалена или заблокирована.")

    await message.reply(
        f"🗓️ Дата регистрации пользователя {mention}:\n"
        f"✨ {reg_date}"
    )


@labeler.message(CommandRule(["админы", "администраторы", "admins", "administrators"], prefixes=("/",)))
async def cmd_admins(message: Message):
    """Вывод списка администраторов и главного администратора беседы"""
    if message.peer_id < 2000000000:
        return await message.reply("❌ Команда доступна только в беседах!")

    peer_id = message.peer_id
    chat = await Repository.get_chat(peer_id)
    owner_id = chat.get("owner_id") if chat else None

    admin_ids = await Repository.get_members_by_role(peer_id, Role.ADMIN)

    lines = ["⭐ Администрация беседы:\n"]

    if owner_id:
        owner_mention = await get_user_mention(owner_id, message.ctx_api)
        lines.append(f"👑 Спец администратор: {owner_mention}")
    else:
        lines.append("👑 Спец администратор: не назначен (напишите /start)")

    if admin_ids:
        lines.append(f"\n⭐ Администраторы ({len(admin_ids)}):")
        for i, uid in enumerate(admin_ids, start=1):
            mention = await get_user_mention(uid, message.ctx_api)
            lines.append(f"{i}. {mention}")
    else:
        lines.append("\n⭐ Администраторы: нет назначенных")

    await message.reply("\n".join(lines))


@labeler.message(CommandRule(["модераторы", "модеры", "moders", "moderators"], prefixes=("/",)))
async def cmd_moderators(message: Message):
    """Вывод списка модераторов беседы"""
    if message.peer_id < 2000000000:
        return await message.reply("❌ Команда доступна только в беседах!")

    peer_id = message.peer_id
    moder_ids = await Repository.get_members_by_role(peer_id, Role.MODERATOR)

    if not moder_ids:
        return await message.reply("🛡️ В этой беседе пока нет назначенных модераторов.")

    lines = [f"🛡️ Модераторы беседы ({len(moder_ids)}):\n"]
    for i, uid in enumerate(moder_ids, start=1):
        mention = await get_user_mention(uid, message.ctx_api)
        lines.append(f"{i}. {mention}")

    await message.reply("\n".join(lines))


@labeler.message(CommandRule(["команды", "help", "помощь"]))
async def cmd_help(message: Message):
    """Выводит список доступных пользователю команд с учетом его роли"""
    peer_id = message.peer_id
    user_id = message.from_id
    role = await Repository.get_member_role(peer_id, user_id) if peer_id > 2000000000 else Role.USER

    mention = await get_user_mention(user_id, message.ctx_api)

    lines = [
        f"📋 Список доступных команд для {mention}",
        f"Ваш статус: {Role.title(role)}\n"
    ]

    # Общие команды (доступны всем)
    lines.extend([
        "🔹 Общие команды:",
        "▫️ /тут (алиас: /ping) — проверка работы бота",
        "▫️ /stata [ID] (алиасы: /стата, /статистика) — статистика участника в беседе",
        "▫️ /reg [ID] (алиасы: /рег, /регистрация) — дата регистрации страницы в ВК",
        "▫️ /number of warnings [ID] (алиасы: /варны, /warns) — количество варнов",
        "▫️ /админы (алиасы: /admins, /администраторы) — список администрации",
        "▫️ /модераторы (алиасы: /moders, /модеры) — список модераторов",
        "▫️ /команды (алиасы: /help, /помощь) — список команд",
        "▫️ /инструкция (алиас: /instruction) — фото-инструкция по настройке бота",
        ""
    ])

    # Команды модератора (уровень 1+)
    if role >= Role.MODERATOR:
        lines.extend([
            "🛡️ Команды модератора (1 ур.):",
            "▫️ /kick [ID] [причина] (алиас: /кик) — исключить участника",
            "▫️ /warn [ID] [причина] (алиас: /варн) — выдать варн (3 варна = бан)",
            "▫️ /unwarn [ID] (алиасы: /анварн, /снятьварн) — снять варн",
            "▫️ /warnings in the chat (алиасы: /варнлист, /warnlist) — список нарушителей",
            "▫️ /mute [ID] [время] [причина] (алиас: /мут) — выдать мут (напр. 30m Спам)",
            "▫️ /unmute [ID] (алиасы: /размут, /снятьмут) — досрочно снять мут",
            ""
        ])

    # Команды администратора (уровень 2+)
    if role >= Role.ADMIN:
        lines.extend([
            "⭐ Команды администратора (2 ур.):",
            "▫️ /moder [ID] (алиасы: +moder, /модер) — назначить модератора",
            "▫️ /unmoder [ID] (алиасы: -moder, /размодер) — снять модератора",
            "▫️ /Внимание [текст] (алиасы: /внимание, /all) — общий сбор участников",
            "▫️ /Тишина (алиасы: /тишина, /silence) — режим тишины",
            "▫️ /ban [ID] [причина] (алиас: /бан) — заблокировать участника",
            "▫️ /unban [ID] (алиас: /разбан) — разблокировать участника",
            "▫️ /banlist (алиас: /банлист) — список заблокированных",
            "▫️ /getban [ID] (алиас: /гетбан) — информация о блокировке",
            "▫️ /запреты (алиас: /rules) — просмотр матрицы запретов чата",
            "▫️ /запрет <название> <действие> — настройка наказания (кик/мут/пред/бан/разрешено)",
            "▫️ /банворды, /банворд, /разбанворд — управление списком запрещенных слов",
            ""
        ])

    # Команды спец администратора (уровень 3)
    if role >= Role.OWNER:
        lines.extend([
            "👑 Команды Спец администратора (3 ур.):",
            "▫️ /start (алиас: /старт) — инициализация беседы (назначение Спец админа)",
            "▫️ /admin [ID] (алиасы: +admin, /админ) — назначить администратора",
            "▫️ /unadmin [ID] (алиасы: -admin, /разадмин) — снять администратора",
            "▫️ /приветствие [текст | выкл | вкл] (алиас: /welcome) — настройка приветствия",
            "▫️ /акик [ID] [причина] (алиас: /allkick) — исключить участника из всех ваших бесед",
            "▫️ /demote (алиас: /расформировать) — расформировать беседу (кик обычных)",
            ""
        ])

    lines.append("💡 Подсказка: указывать ID можно через ответ на сообщение (reply), ссылку или @упоминание.")

    await message.reply("\n".join(lines))


@labeler.message(CommandRule(["инструкция", "instruction"]))
async def cmd_instruction(message: Message):
    """Отправка фото-инструкции по настройке бота"""
    from handlers.events import send_bot_welcome_instruction
    await send_bot_welcome_instruction(message)
