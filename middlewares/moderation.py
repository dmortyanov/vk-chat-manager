import time
import logging
from vkbottle import BaseMiddleware
from vkbottle.bot import Message
from config import Role
from database.repository import Repository
from utils.formatters import get_user_mention, plural_ru
from utils.security_rules import check_message_violations, get_effective_rule_action

logger = logging.getLogger(__name__)


class ModerationMiddleware(BaseMiddleware[Message]):
    """
    Middleware для:
    1. Учета статистики сообщений участников (/stata)
    2. Сохранения CMID сообщений для функции быстрой очистки чата
    3. Проверки активного мута (/mute) и удаления сообщений нарушителя
    4. Проверки режима тишины (/Тишина) и удаления сообщений обычных пользователей
    5. Автоматической проверки 24 правил безопасности чата (вложения, ссылки, мат, банворды и т.д.)
    """

    async def pre(self):
        message = self.event
        logger.info(f"📩 Входящее сообщение [peer={message.peer_id}, from={message.from_id}]: {message.text!r}")

        # Проверяем, что событие происходит в групповой беседе (peer_id > 2000000000)
        if message.peer_id < 2000000000:
            return

        user_id = message.from_id
        peer_id = message.peer_id

        # Если сообщение от сообщества (отрицательный ID)
        if user_id <= 0:
            return

        cmid = message.conversation_message_id

        # 1. Учитываем статистику сообщений и сохраняем CMID для очистки
        try:
            await Repository.increment_messages(peer_id, user_id)
            if cmid:
                await Repository.save_message_cmid(peer_id, user_id, cmid)
        except Exception as e:
            logger.error(f"Ошибка сохранения сообщения пользователя {user_id}: {e}")

        # 2. Проверяем активный мут пользователя
        is_muted_user = False
        try:
            if await Repository.is_muted(peer_id, user_id):
                is_muted_user = True
                if cmid:
                    await message.ctx_api.messages.delete(
                        cmids=[cmid],
                        peer_id=peer_id,
                        delete_for_all=True
                    )
        except Exception as e:
            logger.warning(f"Не удалось удалить сообщение заглушенного пользователя {user_id}: {e}")

        if is_muted_user:
            self.stop("Пользователь заглушен")
            return

        # 3. Проверяем режим тишины в беседе
        role = await Repository.get_member_role(peer_id, user_id)
        silence_active = False
        try:
            chat = await Repository.get_chat(peer_id)
            if chat and chat.get("silence_mode") == 1:
                # Если обычный участник (роль 0) — удаляем сообщение
                if role < Role.MODERATOR:
                    silence_active = True
                    if cmid:
                        await message.ctx_api.messages.delete(
                            cmids=[cmid],
                            peer_id=peer_id,
                            delete_for_all=True
                        )
        except Exception as e:
            logger.warning(f"Ошибка проверки режима тишины в чате {peer_id}: {e}")

        if silence_active:
            self.stop("Режим тишины включен")
            return

        # 4. Проверка правил безопасности и матрицы запретов (только для обычных участников role=0)
        violation_stopped = False
        if role < Role.MODERATOR:
            try:
                custom_rules = await Repository.get_chat_rules(peer_id)
                banwords = await Repository.get_banwords(peer_id)

                violation = check_message_violations(message, custom_rules, banwords)
                if violation:
                    rule_key, action, reason = violation
                    violation_stopped = True

                    # Удаляем сообщение с нарушением
                    if cmid:
                        try:
                            await message.ctx_api.messages.delete(
                                cmids=[cmid],
                                peer_id=peer_id,
                                delete_for_all=True
                            )
                        except Exception:
                            pass

                    target_mention = await get_user_mention(user_id, message.ctx_api)
                    chat_id = peer_id - 2000000000

                    # 4.1. Действие: ПРЕД (Варн)
                    if action == "пред":
                        new_warns = await Repository.add_warn(peer_id, user_id, 0, f"Нарушение запрета ({rule_key})")
                        if new_warns >= 3:
                            # Проверяем действие для макспредов
                            max_act = get_effective_rule_action("макспреды", custom_rules)
                            await Repository.reset_warns(peer_id, user_id)

                            if max_act == "бан":
                                await Repository.add_ban(peer_id, user_id, 0, f"3/3 варнов: {reason}")
                                try:
                                    await message.ctx_api.messages.remove_chat_user(chat_id=chat_id, member_id=user_id)
                                    await message.answer(
                                        f"🚫 Пользователь {target_mention} набрал 3/3 предупреждений и заблокирован в беседе!\n"
                                        f"📝 Причина: {reason}"
                                    )
                                except Exception:
                                    pass
                            else:
                                try:
                                    await message.ctx_api.messages.remove_chat_user(chat_id=chat_id, member_id=user_id)
                                    await message.answer(
                                        f"🚪 Пользователь {target_mention} набрал 3/3 предупреждений и был исключен из беседы!\n"
                                        f"📝 Причина: {reason}"
                                    )
                                except Exception:
                                    pass
                        else:
                            left = 3 - new_warns
                            left_str = f"{left} {plural_ru(left, ('предупреждение', 'предупреждения', 'предупреждений'))}"
                            await message.answer(
                                f"⚠️ {target_mention}, нарушение правил беседы ({reason})!\n"
                                f"Вам выдано предупреждение ({new_warns}/3).\n"
                                f"⏳ До исключения осталось: {left_str}"
                            )

                    # 4.2. Действие: МУТ (Заглушка на 30 мин)
                    elif action == "мут":
                        mute_until = int(time.time()) + 1800  # 30 минут
                        await Repository.set_mute(peer_id, user_id, mute_until)
                        await message.answer(
                            f"🔇 {target_mention} получил заглушку на 30 минут.\n"
                            f"📝 Причина: {reason}"
                        )

                    # 4.3. Действие: КИК (Исключение)
                    elif action == "кик":
                        try:
                            await message.ctx_api.messages.remove_chat_user(chat_id=chat_id, member_id=user_id)
                            await message.answer(
                                f"🚪 {target_mention} был исключен из беседы!\n"
                                f"📝 Причина: {reason}"
                            )
                        except Exception as e:
                            logger.error(f"Не удалось кикнуть нарушителя {user_id}: {e}")

                    # 4.4. Действие: БАН (Блокировка с киком)
                    elif action == "бан":
                        await Repository.add_ban(peer_id, user_id, 0, reason)
                        try:
                            await message.ctx_api.messages.remove_chat_user(chat_id=chat_id, member_id=user_id)
                            await message.answer(
                                f"🔒 {target_mention} был заблокирован и исключен из беседы!\n"
                                f"📝 Причина: {reason}"
                            )
                        except Exception as e:
                            logger.error(f"Не удалось забанить нарушителя {user_id}: {e}")

            except Exception as e:
                logger.error(f"Ошибка проверки правил безопасности в беседе {peer_id}: {e}")

        if violation_stopped:
            self.stop("Нарушение правил безопасности")
            return
