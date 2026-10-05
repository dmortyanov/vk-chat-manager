from vkbottle.bot import BotLabeler, Message
from config import Role
from database.repository import Repository
from utils.rules import CommandRule
from utils.resolver import resolve_target_and_args
from utils.formatters import get_user_mention, format_msk_datetime
from utils.permissions import check_user_role, is_user_in_chat

labeler = BotLabeler()


@labeler.message(CommandRule(["+moder", "+модер", "+moders", "moder", "модер", "moders"], prefixes=("", "/")))
async def cmd_promote_moder(message: Message):
    """Назначение модератора беседы"""
    if message.peer_id < 2000000000:
        return await message.reply("❌ Команда доступна только в беседах!")

    caller_role = await check_user_role(message.peer_id, message.from_id)
    if caller_role < Role.ADMIN:
        return

    target_id, _ = await resolve_target_and_args(message, message.ctx_api, command_name="+moder")
    if not target_id:
        return await message.reply("❌ Укажите ID пользователя для назначения модератором (ответом на сообщение, ссылкой или @упоминанием).")

    if not await is_user_in_chat(message.peer_id, target_id, message.ctx_api):
        return await message.reply("❌ Данного пользователя нет в этой беседе!")

    if target_id == message.from_id:
        return await message.reply("❌ Вы не можете изменить права самому себе!")

    target_role = await check_user_role(message.peer_id, target_id)
    if target_role >= Role.ADMIN and caller_role <= target_role:
        return await message.reply("❌ Нельзя изменить статус пользователю с равными или более высокими правами!")

    await Repository.set_member_role(message.peer_id, target_id, Role.MODERATOR)

    target_mention = await get_user_mention(target_id, message.ctx_api)
    admin_mention = await get_user_mention(message.from_id, message.ctx_api)

    await message.answer(
        f"🛡️ Пользователь {target_mention} успешно назначен Модератором беседы!\n"
        f"👑 Назначил: {admin_mention}"
    )


@labeler.message(CommandRule(["-moder", "-модер", "-moders", "unmoder", "размодер"], prefixes=("", "/")))
async def cmd_demote_moder(message: Message):
    """Снятие прав модератора"""
    if message.peer_id < 2000000000:
        return await message.reply("❌ Команда доступна только в беседах!")

    caller_role = await check_user_role(message.peer_id, message.from_id)
    if caller_role < Role.ADMIN:
        return

    target_id, _ = await resolve_target_and_args(message, message.ctx_api, command_name="-moder")
    if not target_id:
        return await message.reply("❌ Укажите ID пользователя для снятия прав модератора.")

    if not await is_user_in_chat(message.peer_id, target_id, message.ctx_api):
        return await message.reply("❌ Данного пользователя нет в этой беседе!")

    target_role = await check_user_role(message.peer_id, target_id)
    if target_role != Role.MODERATOR:
        return await message.reply("❌ Данный пользователь не является модератором беседы!")

    await Repository.set_member_role(message.peer_id, target_id, Role.USER)

    target_mention = await get_user_mention(target_id, message.ctx_api)
    admin_mention = await get_user_mention(message.from_id, message.ctx_api)

    await message.answer(
        f"👤 С пользователя {target_mention} сняты полномочия Модератора.\n"
        f"👑 Действие выполнил: {admin_mention}"
    )


@labeler.message(CommandRule(["Внимание", "внимание", "all"]))
async def cmd_attention(message: Message):
    """Созыв всех участников беседы"""
    if message.peer_id < 2000000000:
        return await message.reply("❌ Команда доступна только в беседах!")

    caller_role = await check_user_role(message.peer_id, message.from_id)
    if caller_role < Role.ADMIN:
        return

    _, notice_text = await resolve_target_and_args(message, message.ctx_api, command_name="внимание")
    notice_text = notice_text.strip() or "Общий сбор участников беседы!"

    admin_mention = await get_user_mention(message.from_id, message.ctx_api)

    try:
        members_resp = await message.ctx_api.messages.get_conversation_members(peer_id=message.peer_id)
        users = [item.member_id for item in members_resp.items if item.member_id > 0 and item.member_id != message.from_id]

        if not users:
            return await message.answer(f"📢 Внимание от {admin_mention}:\n\n{notice_text}")

        chunk_size = 50
        chunks = [users[i:i + chunk_size] for i in range(0, len(users), chunk_size)]

        for idx, chunk in enumerate(chunks):
            mentions = "".join([f"[id{uid}|&#8203;]" for uid in chunk])
            if idx == 0:
                await message.answer(
                    f"📢 ВНИМАНИЕ ВСЕМ УЧАСТНИКАМ! 📢\n"
                    f"👑 Объявление от администратора {admin_mention}:\n\n"
                    f"{notice_text}\n{mentions}"
                )
            else:
                await message.answer(f"📢 Призыв (продолжение):{mentions}")

    except Exception as e:
        await message.answer(
            f"📢 ВНИМАНИЕ ВСЕМ! (@all)\n"
            f"👑 Объявление от администратора {admin_mention}:\n\n"
            f"{notice_text}"
        )


@labeler.message(CommandRule(["Тишина", "тишина", "silence"]))
async def cmd_silence(message: Message):
    """Включение / выключение режима тишины в беседе"""
    if message.peer_id < 2000000000:
        return await message.reply("❌ Команда доступна только в беседах!")

    caller_role = await check_user_role(message.peer_id, message.from_id)
    if caller_role < Role.ADMIN:
        return

    chat = await Repository.get_or_create_chat(message.peer_id)
    current_mode = chat.get("silence_mode", 0)
    new_mode = 0 if current_mode == 1 else 1

    await Repository.set_silence(message.peer_id, bool(new_mode))

    admin_mention = await get_user_mention(message.from_id, message.ctx_api)

    if new_mode == 1:
        await message.answer(
            f"🤫 РЕЖИМ ТИШИНЫ ВКЛЮЧЕН!\n"
            f"👑 Администратор: {admin_mention}\n\n"
            f"⚠️ Теперь писать в беседу разрешено ТОЛЬКО модераторам и администраторам.\n"
            f"Сообщения обычных участников будут автоматически удаляться ботом."
        )
    else:
        await message.answer(
            f"🗣️ РЕЖИМ ТИШИНЫ ВЫКЛЮЧЕН!\n"
            f"👑 Администратор: {admin_mention}\n\n"
            f"✨ Беседа снова открыта для общения всех участников."
        )


@labeler.message(CommandRule(["ban", "бан"]))
async def cmd_ban(message: Message):
    """Блокировка пользователя в беседе (доступно Администраторам 2+ ур.)"""
    if message.peer_id < 2000000000:
        return await message.reply("❌ Команда доступна только в беседах!")

    caller_role = await check_user_role(message.peer_id, message.from_id)
    if caller_role < Role.ADMIN:
        return

    target_id, reason = await resolve_target_and_args(message, message.ctx_api, command_name="ban")
    if not target_id:
        return await message.reply("❌ Укажите ID пользователя для блокировки (ответом, ссылкой, @упоминанием или ID).")

    if target_id == message.from_id:
        return await message.reply("❌ Вы не можете заблокировать самого себя!")

    target_role = await check_user_role(message.peer_id, target_id)
    if target_role == Role.OWNER:
        return await message.reply("❌ Нельзя заблокировать Спец администратора беседы!")
    if caller_role <= target_role:
        return await message.reply(f"❌ Вы не можете заблокировать пользователя с равным или более высоким статусом ({Role.title(target_role)})!")

    reason = reason.strip() or "Нарушение правил беседы"
    await Repository.add_ban(message.peer_id, target_id, message.from_id, reason)

    # Если пользователь сейчас в беседе, исключаем его
    chat_id = message.peer_id - 2000000000
    try:
        await message.ctx_api.messages.remove_chat_user(chat_id=chat_id, member_id=target_id)
    except Exception:
        pass  # Пользователя могло уже не быть в беседе (превентивный бан)

    target_mention = await get_user_mention(target_id, message.ctx_api)
    admin_mention = await get_user_mention(message.from_id, message.ctx_api)

    await message.answer(
        f"🔒 Пользователь {target_mention} успешно заблокирован в беседе!\n"
        f"👑 Администратор: {admin_mention}\n"
        f"📝 Причина: {reason}\n"
        f"🚪 Доступ в беседу для него закрыт."
    )


@labeler.message(CommandRule(["unban", "разбан"]))
async def cmd_unban(message: Message):
    """Разблокировка пользователя в беседе (не требует нахождения в беседе)"""
    if message.peer_id < 2000000000:
        return await message.reply("❌ Команда доступна только в беседах!")

    caller_role = await check_user_role(message.peer_id, message.from_id)
    if caller_role < Role.ADMIN:
        return

    target_id, _ = await resolve_target_and_args(message, message.ctx_api, command_name="unban")
    if not target_id:
        return await message.reply("❌ Укажите ID пользователя для разблокировки (ссылкой, @упоминанием или ID).")

    success = await Repository.remove_ban(message.peer_id, target_id)
    target_mention = await get_user_mention(target_id, message.ctx_api)
    admin_mention = await get_user_mention(message.from_id, message.ctx_api)

    if success:
        await message.answer(
            f"🔓 Пользователь {target_mention} успешно разблокирован в беседе!\n"
            f"👑 Администратор: {admin_mention}\n"
            f"✨ Теперь он может снова вступить в беседу."
        )
    else:
        await message.reply(f"ℹ️ Пользователь {target_mention} не найден в списке заблокированных.")


@labeler.message(CommandRule(["banlist", "банлист"]))
async def cmd_banlist(message: Message):
    """Список заблокированных пользователей в беседе"""
    if message.peer_id < 2000000000:
        return await message.reply("❌ Команда доступна только в беседах!")

    caller_role = await check_user_role(message.peer_id, message.from_id)
    if caller_role < Role.ADMIN:
        return

    bans = await Repository.get_banlist(message.peer_id)
    if not bans:
        return await message.reply("✨ В списке заблокированных участников этой беседы никого нет.")

    lines = ["🔒 Список заблокированных участников беседы:\n"]
    for idx, b in enumerate(bans, 1):
        target_m = await get_user_mention(b["user_id"], message.ctx_api, fallback_name=f"ID {b['user_id']}")
        lines.append(f"{idx}. {target_m} — Причина: {b['reason']}")

    lines.append("\n💡 Для разблокировки используйте: -ban [ID]")
    await message.reply("\n".join(lines))


@labeler.message(CommandRule(["getban", "гетбан"]))
async def cmd_getban(message: Message):
    """Просмотр статуса блокировки конкретного пользователя"""
    if message.peer_id < 2000000000:
        return await message.reply("❌ Команда доступна только в беседах!")

    caller_role = await check_user_role(message.peer_id, message.from_id)
    if caller_role < Role.ADMIN:
        return

    target_id, _ = await resolve_target_and_args(message, message.ctx_api, command_name="getban")
    if not target_id:
        return await message.reply("❌ Укажите ID пользователя (ссылкой, @упоминанием или ID).")

    ban = await Repository.get_ban(message.peer_id, target_id)
    target_mention = await get_user_mention(target_id, message.ctx_api)

    if not ban:
        return await message.reply(f"ℹ️ Пользователь {target_mention} не заблокирован в этой беседе.")

    admin_mention = await get_user_mention(ban["admin_id"], message.ctx_api, fallback_name=f"ID {ban['admin_id']}")
    ban_date = format_msk_datetime(ban["created_at"])

    await message.reply(
        f"🔒 Информация о блокировке {target_mention}:\n\n"
        f"👮 Заблокировал: {admin_mention}\n"
        f"📝 Причина: {ban['reason']}\n"
        f"📅 Дата блокировки: {ban_date}"
    )
