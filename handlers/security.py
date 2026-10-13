import json
import logging
from vkbottle.bot import BotLabeler, Message, MessageEvent
from vkbottle import Keyboard, KeyboardButtonColor, Callback, Text, GroupEventType
from config import Role
from database.repository import Repository
from utils.rules import CommandRule, BOT_MENTION_REGEX
from utils.permissions import check_user_role
from utils.security_rules import (
    SECURITY_RULES,
    VALID_ACTIONS,
    normalize_action,
    normalize_rule_key,
    format_rules_menu,
    format_action_display,
    get_effective_rule_action,
)

logger = logging.getLogger(__name__)
labeler = BotLabeler()


def get_bottom_keyboard() -> str:
    """Возвращает пустую клавиатуру для гарантированного скрытия нижней панели"""
    return Keyboard(inline=False, one_time=True).get_json()


def get_rules_main_keyboard() -> str:
    """Генерирует инлайн-клавиатуру с кнопкой 'Настроить запреты' как на скриншоте ТЗ"""
    kb = (
        Keyboard(inline=True)
        .add(
            Callback("Настроить запреты", payload=json.dumps({"cmd": "sec_cats"})),
            color=KeyboardButtonColor.SECONDARY
        )
    )
    return kb.get_json()


def get_categories_keyboard() -> str:
    """Инлайн-клавиатура выбора категорий запретов"""
    kb = (
        Keyboard(inline=True)
        .add(Callback("📁 Вложения", payload=json.dumps({"cmd": "sec_cat", "cat": "Вложения"})), color=KeyboardButtonColor.PRIMARY)
        .add(Callback("🌐 Ссылки", payload=json.dumps({"cmd": "sec_cat", "cat": "Посты и ссылки"})), color=KeyboardButtonColor.PRIMARY)
        .row()
        .add(Callback("⚡ Действия", payload=json.dumps({"cmd": "sec_cat", "cat": "Действия"})), color=KeyboardButtonColor.PRIMARY)
        .add(Callback("⚠️ Нарушения", payload=json.dumps({"cmd": "sec_cat", "cat": "Нарушения"})), color=KeyboardButtonColor.PRIMARY)
        .row()
        .add(Callback("🔙 Назад к списку", payload=json.dumps({"cmd": "sec_main"})), color=KeyboardButtonColor.SECONDARY)
    )
    return kb.get_json()


def get_category_rules_keyboard(category: str, custom_rules: dict) -> str:
    """Клавиатура для переключения правил в конкретной категории"""
    kb = Keyboard(inline=True)
    count = 0
    for key, r_def in SECURITY_RULES.items():
        if r_def.category != category:
            continue
        curr_act = get_effective_rule_action(key, custom_rules)
        # Сокращенная индикация для компактной кнопки: "фото: выкл", "инвайт: пред"
        btn_label = f"{key}: {curr_act[:4]}"
        kb.add(
            Callback(btn_label, payload=json.dumps({"cmd": "sec_toggle", "cat": category, "rule": key})),
            color=KeyboardButtonColor.SECONDARY if curr_act == "разрешено" else KeyboardButtonColor.NEGATIVE
        )
        count += 1
        if count % 2 == 0:
            kb.row()

    if count % 2 != 0:
        kb.row()
    kb.add(Callback("🔙 Назад к категориям", payload=json.dumps({"cmd": "sec_cats"})), color=KeyboardButtonColor.PRIMARY)
    return kb.get_json()


@labeler.message(CommandRule(["запреты", "правила", "rules", "настроить запреты", "Настроить запреты"], prefixes=("", "/")))
async def cmd_rules(message: Message):
    """Вывод текущей матрицы запретов беседы с инлайн-кнопкой 'Настроить запреты'"""
    if message.peer_id < 2000000000:
        return await message.reply("❌ Команда доступна только в беседах!")

    caller_role = await check_user_role(message.peer_id, message.from_id)
    if caller_role < Role.ADMIN:
        return

    custom_rules = await Repository.get_chat_rules(message.peer_id)
    text = format_rules_menu(custom_rules)
    kb = get_rules_main_keyboard()

    await message.answer(text, keyboard=kb)


@labeler.message(CommandRule(["запрет", "setrule"]))
async def cmd_set_rule(message: Message):
    """
    Изменение наказания для правила безопасности беседы.
    Синтаксис: /запрет <название> <кик/мут/пред/бан/разрешено>
    """
    if message.peer_id < 2000000000:
        return await message.reply("❌ Команда доступна только в беседах!")

    caller_role = await check_user_role(message.peer_id, message.from_id)
    if caller_role < Role.ADMIN:
        return

    text = BOT_MENTION_REGEX.sub("", (message.text or "")).strip()
    parts = text.split()
    if len(parts) < 3:
        return await message.reply(
            "❌ Неверный синтаксис команды!\n\n"
            "Использование: /запрет <название> <кик/мут/пред/бан/разрешено>\n"
            "Пример: /запрет ссылка мут\n"
            "Пример: /запрет инвайт бан\n"
            "Пример: /запрет стикеры разрешено\n\n"
            "💡 Чтобы посмотреть список всех названий, введите: /запреты"
        )

    rule_input = parts[1].strip().lower()
    rule_name = normalize_rule_key(rule_input)

    # Поддержка синтаксиса: /запрет символы 300 мут
    extra_info = ""
    if rule_name == "символы" and len(parts) >= 4 and parts[2].isdigit():
        new_lim = int(parts[2])
        if 1 <= new_lim <= 10000:
            await Repository.set_max_message_length(message.peer_id, new_lim)
            extra_info = f"\n📏 Лимит символов установлен на {new_lim}."
        action_raw = parts[3].strip().lower()
    else:
        action_raw = parts[2].strip().lower()

    if not rule_name or rule_name not in SECURITY_RULES:
        return await message.reply(
            f"❌ Неизвестное правило «{rule_input}»!\n"
            f"Доступные названия: {', '.join(SECURITY_RULES.keys())}"
        )

    action = normalize_action(action_raw)
    if not action or action not in VALID_ACTIONS:
        return await message.reply(
            f"❌ Некорректное действие «{action_raw}»!\n"
            f"Допустимые действия: {', '.join(VALID_ACTIONS)}"
        )

    await Repository.set_chat_rule(message.peer_id, rule_name, action)
    r_def = SECURITY_RULES[rule_name]

    await message.reply(
        f"✅ Наказание для правила «{r_def.title}» успешно обновлено!{extra_info}\n"
        f"⚙️ Текущий статус: {format_action_display(action)}"
    )


@labeler.message(CommandRule(["символы", "лимитсимволов", "длина", "длинасообщения", "лимит"]))
async def cmd_char_limit(message: Message):
    """
    Просмотр и настройка лимита количества символов в сообщении.
    Синтаксис:
    - /символы — просмотр текущего лимита
    - /символы <число> — установка лимита символов (например: /символы 300)
    - /символы <число> <действие> — установка лимита и наказания (например: /символы 300 мут)
    """
    if message.peer_id < 2000000000:
        return await message.reply("❌ Команда доступна только в беседах!")

    caller_role = await check_user_role(message.peer_id, message.from_id)
    if caller_role < Role.ADMIN:
        return

    text = BOT_MENTION_REGEX.sub("", (message.text or "")).strip()
    parts = text.split()
    current_limit = await Repository.get_max_message_length(message.peer_id)
    custom_rules = await Repository.get_chat_rules(message.peer_id)
    curr_act = get_effective_rule_action("символы", custom_rules)

    if len(parts) == 1:
        return await message.reply(
            f"📏 Настройка длины сообщений в беседе:\n\n"
            f"▫️ Текущий лимит: {current_limit} символов\n"
            f"▫️ Наказание за превышение: {format_action_display(curr_act)}\n\n"
            f"💡 Чтобы изменить лимит, введите: /символы <число>\n"
            f"Пример: /символы 300\n"
            f"💡 Чтобы настроить наказание: /запрет символы <кик/мут/пред/бан/разрешено>\n"
            f"Пример: /запрет символы мут"
        )

    raw_num = parts[1].strip()
    if not raw_num.isdigit():
        return await message.reply(
            "❌ Укажите положительное число символов!\n"
            "Пример: /символы 300\n"
            "Пример: /символы 500 мут"
        )

    new_limit = int(raw_num)
    if new_limit < 1 or new_limit > 10000:
        return await message.reply("❌ Лимит символов должен быть в диапазоне от 1 до 10000!")

    await Repository.set_max_message_length(message.peer_id, new_limit)

    action_msg = ""
    if len(parts) >= 3:
        act_raw = parts[2].strip().lower()
        act = normalize_action(act_raw)
        if act and act in VALID_ACTIONS:
            await Repository.set_chat_rule(message.peer_id, "символы", act)
            action_msg = f"\n⚙️ Наказание установлено: {format_action_display(act)}"
        else:
            action_msg = f"\n⚠️ Действие «{act_raw}» не распознано. Текущее наказание: {format_action_display(curr_act)}"
    else:
        if curr_act == "разрешено":
            action_msg = (
                f"\n⚠️ Внимание: сейчас правило «символы» находится в статусе «разрешено» (выключено).\n"
                f"Чтобы включить наказание, введите: /запрет символы мут (или пред/кик/бан)"
            )

    await message.reply(
        f"✅ Лимит символов в сообщении успешно установлен на {new_limit}!{action_msg}"
    )


@labeler.message(CommandRule(["банворды", "banwords"]))
async def cmd_list_banwords(message: Message):
    """Список запрещенных слов в беседе"""
    if message.peer_id < 2000000000:
        return await message.reply("❌ Команда доступна только в беседах!")

    caller_role = await check_user_role(message.peer_id, message.from_id)
    if caller_role < Role.ADMIN:
        return

    words = await Repository.get_banwords(message.peer_id)
    if not words:
        return await message.reply("✨ В этой беседе пока нет добавленных банвордов.")

    words_str = ", ".join(f"«{w}»" for w in words)
    await message.reply(
        f"🔤 Список запрещенных слов беседы ({len(words)}):\n{words_str}\n\n"
        f"Добавить: /банворд <слово>\nУдалить: /разбанворд <слово>"
    )


@labeler.message(CommandRule(["+банворд", "банворд", "addbanword"], prefixes=("", "/")))
async def cmd_add_banword(message: Message):
    """Добавление запрещенного слова в беседу"""
    if message.peer_id < 2000000000:
        return await message.reply("❌ Команда доступна только в беседах!")

    caller_role = await check_user_role(message.peer_id, message.from_id)
    if caller_role < Role.ADMIN:
        return

    text = (message.text or "").strip()
    parts = text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        return await message.reply("❌ Укажите слово для добавления в бан-лист! Пример: /банворд спам")

    word = parts[1].strip().lower()
    ok = await Repository.add_banword(message.peer_id, word)
    if ok:
        await message.reply(f"✅ Слово «{word}» добавлено в список банвордов беседы.")
    else:
        await message.reply(f"ℹ️ Слово «{word}» уже находится в бан-листе.")


@labeler.message(CommandRule(["-банворд", "разбанворд", "delbanword"], prefixes=("", "/")))
async def cmd_del_banword(message: Message):
    """Удаление запрещенного слова из беседы"""
    if message.peer_id < 2000000000:
        return await message.reply("❌ Команда доступна только в беседах!")

    caller_role = await check_user_role(message.peer_id, message.from_id)
    if caller_role < Role.ADMIN:
        return

    text = (message.text or "").strip()
    parts = text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        return await message.reply("❌ Укажите слово для удаления! Пример: /разбанворд спам")

    word = parts[1].strip().lower()
    ok = await Repository.remove_banword(message.peer_id, word)
    if ok:
        await message.reply(f"✅ Слово «{word}» удалено из списка банвордов беседы.")
    else:
        await message.reply(f"❌ Слово «{word}» не найдено в бан-листе беседы.")
