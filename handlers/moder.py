import time
import re
from vkbottle.bot import BotLabeler, Message
from config import Role
from database.repository import Repository
from utils.rules import CommandRule
from utils.resolver import resolve_target_and_args
from utils.formatters import get_user_mention, format_duration, plural_ru, format_msk_datetime
from utils.permissions import can_moderate_target, check_user_role, is_user_in_chat

labeler = BotLabeler()


@labeler.message(CommandRule(["kick", "кик"]))
async def cmd_kick(message: Message):
    """Исключение участника из беседы"""
    if message.peer_id < 2000000000:
        return await message.reply("❌ Команда доступна только в беседах!")

    caller_role = await check_user_role(message.peer_id, message.from_id)
    if caller_role < Role.MODERATOR:
        return

    target_id, reason = await resolve_target_and_args(message, message.ctx_api, command_name="kick")
    if not target_id:
        return await message.reply("❌ Укажите ID пользователя (ответом на сообщение, ссылкой или @упоминанием).")

    allowed, err_msg = await can_moderate_target(message.peer_id, message.from_id, target_id, api=message.ctx_api)
    if not allowed:
        return await message.reply(err_msg)

    reason = reason.strip() or "Не указана"
    target_mention = await get_user_mention(target_id, message.ctx_api)
    admin_mention = await get_user_mention(message.from_id, message.ctx_api)

    chat_id = message.peer_id - 2000000000
    try:
        await message.ctx_api.messages.remove_chat_user(chat_id=chat_id, member_id=target_id)
        await message.answer(
            f"🚪 Пользователь {target_mention} был исключен из беседы.\n"
            f"👮 Модератор: {admin_mention}\n"
            f"📝 Причина: {reason}"
        )
    except Exception as e:
        await message.reply(
            f"❌ Не удалось исключить пользователя. Убедитесь, что бот назначен администратором беседы!\nОшибка: {e}"
        )


@labeler.message(CommandRule(["+warn", "+варн", "warn", "варн"], prefixes=("", "/")))
async def cmd_warn(message: Message):
    """Выдача предупреждения участнику (при 3/3 — авто-кик)"""
    if message.peer_id < 2000000000:
        return await message.reply("❌ Команда доступна только в беседах!")

    caller_role = await check_user_role(message.peer_id, message.from_id)
    if caller_role < Role.MODERATOR:
        return

    target_id, reason = await resolve_target_and_args(message, message.ctx_api, command_name="warn")
    if not target_id:
        return await message.reply("❌ Укажите ID пользователя для выдачи предупреждения (ответом, ссылкой или @упоминанием).")

    allowed, err_msg = await can_moderate_target(message.peer_id, message.from_id, target_id, api=message.ctx_api)
    if not allowed:
        return await message.reply(err_msg)

    reason = reason.strip() or "Нарушение правил беседы"
    new_warns = await Repository.add_warn(message.peer_id, target_id, message.from_id, reason)

    target_mention = await get_user_mention(target_id, message.ctx_api)
    admin_mention = await get_user_mention(message.from_id, message.ctx_api)

    if new_warns >= 3:
        # Автоматический кик и сброс варнов / внесение в бан
        await Repository.reset_warns(message.peer_id, target_id)
        await Repository.add_ban(message.peer_id, target_id, message.from_id, f"Превышение лимита предупреждений (3/3): {reason}")

        chat_id = message.peer_id - 2000000000
        try:
            await message.ctx_api.messages.remove_chat_user(chat_id=chat_id, member_id=target_id)
            await message.answer(
                f"🚫 Пользователь {target_mention} получил 3/3 предупреждений и был исключен из беседы!\n"
                f"📝 Последняя причина: {reason}\n"
                f"🔒 Пользователь заблокирован в беседе."
            )
        except Exception as e:
            await message.answer(
                f"⚠️ Пользователь {target_mention} набрал 3/3 предупреждений, но боту не удалось его исключить.\n"
                f"Проверьте права администратора у бота!\nОшибка: {e}"
            )
    else:
        left = 3 - new_warns
        left_str = f"{left} {plural_ru(left, ('предупреждение', 'предупреждения', 'предупреждений'))}"
        await message.answer(
            f"⚠️ Пользователю {target_mention} выдано предупреждение ({new_warns}/3)!\n"
            f"👮 Модератор: {admin_mention}\n"
            f"📝 Причина: {reason}\n"
            f"⏳ До исключения осталось: {left_str}"
        )


@labeler.message(CommandRule(["-warn", "-варн", "unwarn", "анварн", "снятьварн"], prefixes=("", "/")))
async def cmd_unwarn(message: Message):
    """Снятие предупреждения у пользователя"""
    if message.peer_id < 2000000000:
        return await message.reply("❌ Команда доступна только в беседах!")

    caller_role = await check_user_role(message.peer_id, message.from_id)
    if caller_role < Role.MODERATOR:
        return

    target_id, _ = await resolve_target_and_args(message, message.ctx_api, command_name="unwarn")
    if not target_id:
        return await message.reply("❌ Укажите ID пользователя для снятия предупреждения (ответом, ссылкой или @упоминанием).")

    allowed, err_msg = await can_moderate_target(message.peer_id, message.from_id, target_id, api=message.ctx_api)
    if not allowed:
        return await message.reply(err_msg)

    new_count = await Repository.remove_warn(message.peer_id, target_id)
    target_mention = await get_user_mention(target_id, message.ctx_api)
    admin_mention = await get_user_mention(message.from_id, message.ctx_api)

    await message.answer(
        f"✅ С пользователя {target_mention} снято предупреждение.\n"
        f"👮 Модератор: {admin_mention}\n"
        f"📊 Текущее количество предупреждений: {new_count}/3"
    )


@labeler.message(CommandRule(["warnings in the chat", "варнлист", "warnlist"]))
async def cmd_warnings_in_chat(message: Message):
    """Список всех пользователей в беседе, имеющих предупреждения"""
    if message.peer_id < 2000000000:
        return await message.reply("❌ Команда доступна только в беседах!")

    warned_users = await Repository.get_chat_warned_users(message.peer_id)
    if not warned_users:
        return await message.reply("✨ В этой беседе нет участников с активными предупреждениями!")

    lines = ["📋 Список участников с активными предупреждениями:\n"]
    for idx, row in enumerate(warned_users, 1):
        mention = await get_user_mention(row["user_id"], message.ctx_api)
        lines.append(f"{idx}. {mention} — {row['warns_count']}/3 варнов")

    await message.reply("\n".join(lines))


@labeler.message(CommandRule(["number of warnings", "варны", "warns"]))
async def cmd_number_of_warnings(message: Message):
    """Просмотр количества предупреждений у участника"""
    if message.peer_id < 2000000000:
        return await message.reply("❌ Команда доступна только в беседах!")

    target_id, _ = await resolve_target_and_args(message, message.ctx_api, command_name="number of warnings")
    if not target_id:
        target_id = message.from_id

    if not await is_user_in_chat(message.peer_id, target_id, message.ctx_api):
        return await message.reply("❌ Данного пользователя нет в этой беседе!")

    member = await Repository.get_or_create_member(message.peer_id, target_id)
    warns_count = member.get("warns_count", 0)
    target_mention = await get_user_mention(target_id, message.ctx_api)

    history = await Repository.get_user_warns(message.peer_id, target_id)

    lines = [
        f"⚠️ Предупреждения пользователя {target_mention}:",
        f"Текущие активные варны: {warns_count}/3"
    ]

    if history:
        lines.append("\n📜 Последние записи в истории:")
        for idx, item in enumerate(history[:5], 1):
            admin_m = await get_user_mention(item["admin_id"], message.ctx_api, fallback_name=f"ID {item['admin_id']}")
            warn_date = format_msk_datetime(item.get("created_at"))
            lines.append(f"{idx}. Причина: {item['reason']} (выдал {admin_m}, {warn_date})")

    await message.reply("\n".join(lines))


@labeler.message(CommandRule(["mute", "мут"]))
async def cmd_mute(message: Message):
    """Выдача заглушки (мута) пользователю на X минут"""
    if message.peer_id < 2000000000:
        return await message.reply("❌ Команда доступна только в беседах!")

    caller_role = await check_user_role(message.peer_id, message.from_id)
    if caller_role < Role.MODERATOR:
        return

    target_id, args = await resolve_target_and_args(message, message.ctx_api, command_name="mute")
    if not target_id:
        return await message.reply("❌ Укажите ID пользователя и время мута. Пример: /mute @user 30 Спам")

    allowed, err_msg = await can_moderate_target(message.peer_id, message.from_id, target_id, api=message.ctx_api)
    if not allowed:
        return await message.reply(err_msg)

    # Парсим время и причину из оставшихся аргументов
    minutes = 15
    reason = "Нарушение правил беседы"

    tokens = args.strip().split()
    if tokens:
        time_token = tokens[0]
        match = re.match(r"^(\d+)([mмhчdд]?)$", time_token.lower())
        if match:
            val = int(match.group(1))
            unit = match.group(2)
            if unit in ("h", "ч"):
                minutes = val * 60
            elif unit in ("d", "д"):
                minutes = val * 60 * 24
            else:
                minutes = val
            reason = " ".join(tokens[1:]) or reason
        else:
            reason = " ".join(tokens)

    minutes = max(1, min(minutes, 43200))
    until_ts = int(time.time()) + minutes * 60

    await Repository.set_mute(message.peer_id, target_id, until_ts)

    target_mention = await get_user_mention(target_id, message.ctx_api)
    admin_mention = await get_user_mention(message.from_id, message.ctx_api)
    dur_str = format_duration(minutes)

    await message.answer(
        f"🔇 Пользователю {target_mention} выдана заглушка (мут) на {dur_str}!\n"
        f"👮 Модератор: {admin_mention}\n"
        f"📝 Причина: {reason}\n"
        f"⚠️ Все сообщения пользователя в этот период будут автоматически удаляться ботом."
    )


@labeler.message(CommandRule(["unmute", "размут", "снятьмут"]))
async def cmd_unmute(message: Message):
    """Снятие заглушки (мута) с участника"""
    if message.peer_id < 2000000000:
        return await message.reply("❌ Команда доступна только в беседах!")

    caller_role = await check_user_role(message.peer_id, message.from_id)
    if caller_role < Role.MODERATOR:
        return

    target_id, _ = await resolve_target_and_args(message, message.ctx_api, command_name="unmute")
    if not target_id:
        return await message.reply("❌ Укажите ID пользователя для снятия заглушки (ответом, ссылкой или @упоминанием).")

    allowed, err_msg = await can_moderate_target(message.peer_id, message.from_id, target_id, api=message.ctx_api)
    if not allowed:
        return await message.reply(err_msg)

    await Repository.remove_mute(message.peer_id, target_id)
    target_mention = await get_user_mention(target_id, message.ctx_api)
    admin_mention = await get_user_mention(message.from_id, message.ctx_api)

    await message.answer(
        f"🔊 С пользователя {target_mention} снята заглушка.\n"
        f"👮 Модератор: {admin_mention}\n"
        f"✨ Теперь пользователь снова может писать в беседу."
    )
