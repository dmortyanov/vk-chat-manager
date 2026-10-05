import json
import logging
from vkbottle.bot import BotLabeler, MessageEvent
from vkbottle import GroupEventType, Keyboard, KeyboardButtonColor, Callback
from config import Role
from database.repository import Repository
from utils.permissions import check_user_role
from utils.formatters import get_user_mention
from utils.security_rules import (
    SECURITY_RULES,
    format_rules_menu,
    get_effective_rule_action
)
from handlers.security import (
    get_rules_main_keyboard,
    get_categories_keyboard,
    get_category_rules_keyboard
)

logger = logging.getLogger(__name__)
labeler = BotLabeler()


@labeler.raw_event(GroupEventType.MESSAGE_EVENT, dataclass=MessageEvent)
async def handle_all_message_events(event: MessageEvent):
    """
    Единый диспетчер обработки всех интерактивных callback-кнопок ВКонтакте.
    Всегда отправляет show_snackbar, предотвращая зависание кнопок с индикатором загрузки.
    """
    payload = event.payload
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except Exception:
            payload = {}

    if not isinstance(payload, dict):
        payload = {}

    cmd = str(payload.get("cmd", ""))
    peer_id = event.peer_id
    user_id = event.user_id

    # 1. ОБРАБОТКА МАТРИЦЫ ЗАПРЕТОВ (sec_...)
    if cmd.startswith("sec_"):
        caller_role = await check_user_role(peer_id, user_id)
        if caller_role < Role.ADMIN:
            return await event.show_snackbar("❌ Только администраторы могут настраивать запреты!")

        if cmd == "sec_main":
            custom_rules = await Repository.get_chat_rules(peer_id)
            text = format_rules_menu(custom_rules)
            kb = get_rules_main_keyboard()
            try:
                await event.ctx_api.messages.edit(
                    peer_id=peer_id,
                    conversation_message_id=event.conversation_message_id,
                    message=text,
                    keyboard=kb
                )
            except Exception:
                pass
            return await event.show_snackbar("Запреты беседы")

        elif cmd == "sec_cats":
            kb = get_categories_keyboard()
            try:
                await event.ctx_api.messages.edit(
                    peer_id=peer_id,
                    conversation_message_id=event.conversation_message_id,
                    message="⚙️ Выберите категорию для быстрой настройки запретов кнопками:",
                    keyboard=kb
                )
            except Exception:
                pass
            return await event.show_snackbar("Выбор категории")

        elif cmd == "sec_cat":
            cat = payload.get("cat", "Вложения")
            custom_rules = await Repository.get_chat_rules(peer_id)
            kb = get_category_rules_keyboard(cat, custom_rules)
            try:
                await event.ctx_api.messages.edit(
                    peer_id=peer_id,
                    conversation_message_id=event.conversation_message_id,
                    message=f"⚙️ Категория «{cat}»\nНажимайте на кнопки для переключения (разрешено ➔ пред ➔ мут ➔ кик ➔ бан):",
                    keyboard=kb
                )
            except Exception:
                pass
            return await event.show_snackbar(cat)

        elif cmd == "sec_toggle":
            cat = payload.get("cat", "Вложения")
            rule_key = payload.get("rule")
            if rule_key and rule_key in SECURITY_RULES:
                custom_rules = await Repository.get_chat_rules(peer_id)
                curr_act = get_effective_rule_action(rule_key, custom_rules)
                cycle = ["разрешено", "пред", "мут", "кик", "бан"]
                try:
                    idx = cycle.index(curr_act)
                    next_act = cycle[(idx + 1) % len(cycle)]
                except ValueError:
                    next_act = "пред"

                await Repository.set_chat_rule(peer_id, rule_key, next_act)
                custom_rules[rule_key] = next_act
                kb = get_category_rules_keyboard(cat, custom_rules)
                try:
                    await event.ctx_api.messages.edit(
                        peer_id=peer_id,
                        conversation_message_id=event.conversation_message_id,
                        message=f"⚙️ Категория «{cat}»\nНажимайте на кнопки для переключения (разрешено ➔ пред ➔ мут ➔ кик ➔ бан):",
                        keyboard=kb
                    )
                except Exception:
                    pass
                return await event.show_snackbar(f"{rule_key}: {next_act}")

    # 2. ОБРАБОТКА ВЫХОДА ИЗ БЕСЕДЫ (leave_kick / leave_clean)
    elif cmd in ("leave_kick", "leave_clean", "leave_done", "clean_done"):
        if cmd == "leave_done":
            return await event.show_snackbar("Пользователь уже исключен из беседы!")
        if cmd == "clean_done":
            return await event.show_snackbar("Сообщения пользователя уже очищены!")

        caller_role = await check_user_role(peer_id, user_id)
        if caller_role < Role.MODERATOR:
            return await event.show_snackbar("❌ Только администраторы беседы могут использовать эти кнопки!")

        target_id = payload.get("uid")
        target_mention = await get_user_mention(target_id, event.ctx_api)
        admin_mention = await get_user_mention(user_id, event.ctx_api)

        # 2.1. Нажата кнопка «Кикнуть»
        if cmd == "leave_kick":
            cleaned = int(payload.get("cleaned", 0))
            prev_del_count = int(payload.get("del_count", 0))

            # Исключаем пользователя без бана
            chat_id = peer_id - 2000000000
            try:
                await event.ctx_api.messages.remove_chat_user(chat_id=chat_id, member_id=target_id)
            except Exception:
                pass
            await event.show_snackbar("Пользователь исключен из беседы!")

            if cleaned:
                # Очистка уже была выполнена — теперь завершены оба действия!
                msg_text = (
                    f"🚪 Пользователь {target_mention} покинул беседу.\n"
                    f"🧹 Чат очищен от сообщений ({prev_del_count} шт.).\n"
                    f"❌ Исключен из беседы администратором {admin_mention}."
                )
                kb = Keyboard(inline=True).get_json()  # пустая клавиатура (удаляет инлайн-кнопки)
            else:
                # Очистка еще не выполнена — оставляем кнопку «Очистить»
                msg_text = (
                    f"🚪 Пользователь {target_mention} покинул беседу.\n"
                    f"❌ Исключен из беседы администратором {admin_mention}."
                )
                kb = (
                    Keyboard(inline=True)
                    .add(
                        Callback("Исключен ✅", payload=json.dumps({"cmd": "leave_done"})),
                        color=KeyboardButtonColor.SECONDARY
                    )
                    .add(
                        Callback("Очистить", payload=json.dumps({"cmd": "leave_clean", "uid": target_id, "kicked": 1})),
                        color=KeyboardButtonColor.POSITIVE
                    )
                ).get_json()

            try:
                await event.ctx_api.messages.edit(
                    peer_id=peer_id,
                    conversation_message_id=event.conversation_message_id,
                    message=msg_text,
                    keyboard=kb
                )
            except Exception as e:
                logger.warning(f"Не удалось обновить сообщение выхода: {e}")
            return

        # 2.2. Нажата кнопка «Очистить»
        elif cmd == "leave_clean":
            kicked = int(payload.get("kicked", 0))

            cmids = await Repository.get_user_cmids(peer_id, target_id)
            deleted_count = 0
            if cmids:
                try:
                    chunk_size = 100
                    for i in range(0, len(cmids), chunk_size):
                        chunk = cmids[i:i + chunk_size]
                        await event.ctx_api.messages.delete(
                            cmids=chunk,
                            peer_id=peer_id,
                            delete_for_all=True
                        )
                        deleted_count += len(chunk)
                    await Repository.delete_user_cmids(peer_id, target_id)
                except Exception as e:
                    logger.warning(f"Ошибка при очистке сообщений: {e}")

            await event.show_snackbar(f"Очищено {deleted_count} сообщений!")

            if kicked:
                # Пользователь уже был исключен — теперь завершены оба действия!
                msg_text = (
                    f"🚪 Пользователь {target_mention} покинул беседу.\n"
                    f"❌ Пользователь исключен из беседы.\n"
                    f"🧹 Чат очищен от сообщений ({deleted_count} шт.) администратором {admin_mention}."
                )
                kb = Keyboard(inline=True).get_json()  # пустая клавиатура (удаляет инлайн-кнопки)
            else:
                # Исключение еще не выполнено — оставляем кнопку «Кикнуть»
                msg_text = (
                    f"🚪 Пользователь {target_mention} покинул беседу.\n"
                    f"🧹 Чат очищен от сообщений пользователя ({deleted_count} сообщений за 24ч) администратором {admin_mention}."
                )
                kb = (
                    Keyboard(inline=True)
                    .add(
                        Callback("Кикнуть", payload=json.dumps({"cmd": "leave_kick", "uid": target_id, "cleaned": 1, "del_count": deleted_count})),
                        color=KeyboardButtonColor.NEGATIVE
                    )
                    .add(
                        Callback(f"Очищено ({deleted_count}) ✅", payload=json.dumps({"cmd": "clean_done"})),
                        color=KeyboardButtonColor.SECONDARY
                    )
                ).get_json()

            try:
                await event.ctx_api.messages.edit(
                    peer_id=peer_id,
                    conversation_message_id=event.conversation_message_id,
                    message=msg_text,
                    keyboard=kb
                )
            except Exception as e:
                logger.warning(f"Не удалось обновить сообщение выхода: {e}")
            return

    # 3. РАСФОРМИРОВАНИЕ БЕСЕДЫ (demote)
    elif cmd in ("confirm_demote", "cancel_demote"):
        from handlers.owner import execute_demote
        expected_owner = payload.get("owner_id")
        if user_id != expected_owner:
            return await event.show_snackbar("❌ Только инициатор (Спец админ) может нажать эту кнопку!")

        if cmd == "cancel_demote":
            await event.ctx_api.messages.send(
                peer_id=peer_id,
                random_id=0,
                message="🛡️ Расформирование беседы отменено."
            )
            return await event.show_snackbar("Действие отменено.")

        if cmd == "confirm_demote":
            await event.show_snackbar("Начинаю расформирование беседы...")
            await execute_demote(peer_id, user_id, event.ctx_api)
            return

    # 4. ОБЯЗАТЕЛЬНЫЙ ОТВЕТ НА ЛЮБОЙ ДРУГОЙ EVENT (предотвращает бесконечный лоадер)
    try:
        await event.show_snackbar("Готово")
    except Exception:
        pass
