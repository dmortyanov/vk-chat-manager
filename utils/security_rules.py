import re
from typing import Dict, List, Optional, Tuple, Any

# Регулярные выражения для детекции
URL_REGEX = re.compile(
    r"(?i)\b((?:https?://|www\d{0,3}[.]|[a-z0-9.\-]+[.][a-z]{2,4}/)(?:[^\s()<>]+|\(([^\s()<>]+|(\([^\s()<>]+\)))\))+(?:\(([^\s()<>]+|(\([^\s()<>]+\)))\)|[^\s`!()\[\]{};:'\".,<>?«»“”‘’]))",
    re.IGNORECASE
)
CHAT_INVITE_REGEX = re.compile(
    r"(?i)(?:vk\.me/join/|vk\.com/join/)[a-zA-Z0-9_\-]+",
    re.IGNORECASE
)
COMMUNITY_MENTION_REGEX = re.compile(
    r"(?:\[(?:club|public|event)\d+\|[^\]]+\]|@(?:club|public|event)\d+|(?:vk\.com|vk\.me)/(?:club|public|event)\d+)",
    re.IGNORECASE
)
PUSH_MENTION_REGEX = re.compile(
    r"(?i)(?:@all|@online|\[all\|[^\]]+\]|\[online\|[^\]]+\]|@everyone)",
    re.IGNORECASE
)

# Мат-фильтр (основные корни с вариациями)
MAT_REGEX = re.compile(
    r"(?i)\b([хx][уyеeё][йяеию]|п[иее]зд|бл[яе]|еб[аеёу]|ёб[аеу]|сук[аио]|[гg][аaоo][вv][нn][оo]|ху[еёли]|пид[оа]р|шлюх|чмо|залуп|мудак|ебл|въеб|выеб|доеб|наеб|поеб|подъеб|проеб|перееб|уеб)[а-яa-z0-9]*\b"
)


class SecurityRuleDef:
    def __init__(self, key: str, title: str, category: str, default_action: str = "разрешено"):
        self.key = key
        self.title = title
        self.category = category
        self.default_action = default_action


# 24 правила безопасности чата строго по категориям ТЗ
SECURITY_RULES: Dict[str, SecurityRuleDef] = {
    # Вложения
    "фото": SecurityRuleDef("фото", "🏞️ Фотография", "Вложения", "разрешено"),
    "видео": SecurityRuleDef("видео", "🎬 Видео", "Вложения", "разрешено"),
    "аудио": SecurityRuleDef("аудио", "🎵 Музыка", "Вложения", "разрешено"),
    "файлы": SecurityRuleDef("файлы", "📂 Файл/гифка", "Вложения", "разрешено"),
    "стикеры": SecurityRuleDef("стикеры", "💟 Стикер", "Вложения", "разрешено"),
    "гс": SecurityRuleDef("гс", "📞 Голосовое сообщение", "Вложения", "разрешено"),
    "кружочки": SecurityRuleDef("кружочки", "🗿 Видеосообщение", "Вложения", "разрешено"),
    "опрос": SecurityRuleDef("опрос", "📊 Опрос", "Вложения", "разрешено"),
    "сторис": SecurityRuleDef("сторис", "📱 История", "Вложения", "разрешено"),

    # Посты и ссылки
    "ссылка": SecurityRuleDef("ссылка", "🌐 Ссылки в сообщении", "Посты и ссылки", "разрешено"),
    "группа": SecurityRuleDef("группа", "👥 Упоминание сообщества", "Посты и ссылки", "разрешено"),
    "репост": SecurityRuleDef("репост", "📢 Репост", "Посты и ссылки", "разрешено"),
    "коммент": SecurityRuleDef("коммент", "📝 Комментарий к посту", "Посты и ссылки", "разрешено"),
    "инвайт": SecurityRuleDef("инвайт", "💬 Ссылка на чат", "Посты и ссылки", "пред"),

    # Действия
    "капс": SecurityRuleDef("капс", "🔠 Капс", "Действия", "разрешено"),
    "реакции": SecurityRuleDef("реакции", "🤩 Реакция на сообщение", "Действия", "разрешено"),
    "бомбочка": SecurityRuleDef("бомбочка", "💣 Исчезающее сообщение", "Действия", "разрешено"),
    "скрины": SecurityRuleDef("скрины", "💻 Скриншот", "Действия", "разрешено"),
    "закреп": SecurityRuleDef("закреп", "📌 Установка закрепа", "Действия", "разрешено"),
    "пуш": SecurityRuleDef("пуш", "📣 Упоминание пользователей", "Действия", "разрешено"),

    # Нарушения
    "банворд": SecurityRuleDef("банворд", "🔤 Банворд в сообщении", "Нарушения", "кик"),
    "банстикер": SecurityRuleDef("банстикер", "🛑 Отправка запрещённого стикера", "Нарушения", "пред"),
    "макспреды": SecurityRuleDef("макспреды", "⚠️ Макс. кол-во предупреждений", "Нарушения", "бан"),
    "мат": SecurityRuleDef("мат", "🤬 Мат в сообщении", "Нарушения", "разрешено"),
}

VALID_ACTIONS = ("разрешено", "пред", "мут", "кик", "бан")
ACTION_ALIASES = {
    "разрешено": "разрешено",
    "разрешить": "разрешено",
    "выкл": "разрешено",
    "off": "разрешено",
    "allow": "разрешено",
    "none": "разрешено",

    "пред": "пред",
    "варн": "пред",
    "предупреждение": "пред",
    "warn": "пред",

    "мут": "мут",
    "mute": "мут",
    "заглушка": "мут",

    "кик": "кик",
    "kick": "кик",
    "исключить": "кик",

    "бан": "бан",
    "ban": "бан",
    "блок": "бан",
}

RULE_NAME_ALIASES = {
    "фото": "фото",
    "фотография": "фото",
    "фотографии": "фото",
    "photo": "фото",
    "картинка": "фото",
    "картинки": "фото",

    "видео": "видео",
    "видеозапись": "видео",
    "видеозаписи": "видео",
    "video": "видео",

    "аудио": "аудио",
    "музыка": "аудио",
    "трек": "аудио",
    "треки": "аудио",
    "audio": "аудио",
    "music": "аудио",

    "файлы": "файлы",
    "файл": "файлы",
    "документ": "файлы",
    "документы": "файлы",
    "гиф": "файлы",
    "гифка": "файлы",
    "гифки": "файлы",
    "gif": "файлы",
    "file": "файлы",
    "files": "файлы",
    "doc": "файлы",

    "стикеры": "стикеры",
    "стикер": "стикеры",
    "наклейка": "стикеры",
    "наклейки": "стикеры",
    "sticker": "стикеры",
    "stickers": "стикеры",

    "гс": "гс",
    "голосовые": "гс",
    "голосовое": "гс",
    "голосовыесообщения": "гс",
    "аудиосообщение": "гс",
    "voice": "гс",

    "кружочки": "кружочки",
    "кружок": "кружочки",
    "кружочек": "кружочки",
    "видеосообщение": "кружочки",
    "видеосообщения": "кружочки",
    "round": "кружочки",

    "опрос": "опрос",
    "опросы": "опрос",
    "голосование": "опрос",
    "poll": "опрос",

    "сторис": "сторис",
    "история": "сторис",
    "истории": "сторис",
    "story": "сторис",
    "stories": "сторис",

    "ссылка": "ссылка",
    "ссылки": "ссылка",
    "link": "ссылка",
    "url": "ссылка",

    "группа": "группа",
    "группы": "группа",
    "сообщество": "группа",
    "сообщества": "группа",
    "паблик": "группа",
    "паблики": "группа",
    "group": "группа",

    "репост": "репост",
    "репосты": "репост",
    "repost": "репост",

    "коммент": "коммент",
    "комментарий": "коммент",
    "комментарии": "коммент",
    "комменты": "коммент",
    "comment": "коммент",

    "инвайт": "инвайт",
    "инвайты": "инвайт",
    "чат": "инвайт",
    "беседа": "инвайт",
    "ссылканачат": "инвайт",
    "invite": "инвайт",

    "капс": "капс",
    "caps": "капс",

    "реакции": "реакции",
    "реакция": "реакции",
    "reaction": "реакции",

    "бомбочка": "бомбочка",
    "бомбочки": "бомбочка",
    "исчезающие": "бомбочка",
    "исчезающее": "бомбочка",

    "скрины": "скрины",
    "скрин": "скрины",
    "скриншот": "скрины",
    "скриншоты": "скрины",
    "screenshot": "скрины",

    "закреп": "закреп",
    "закрепление": "закреп",
    "пин": "закреп",
    "pin": "закреп",

    "пуш": "пуш",
    "упоминания": "пуш",
    "упоминание": "пуш",
    "онлайн": "пуш",
    "все": "пуш",
    "all": "пуш",
    "online": "пуш",
    "push": "пуш",

    "банворд": "банворд",
    "банворды": "банворд",
    "banword": "банворд",

    "банстикер": "банстикер",
    "банстикеры": "банстикер",
    "bansticker": "банстикер",

    "макспреды": "макспреды",
    "максварны": "макспреды",
    "варны": "макспреды",
    "преды": "макспреды",
    "maxwarns": "макспреды",

    "мат": "мат",
    "матершина": "мат",
    "ругань": "мат",
    "цензура": "мат",
}


def normalize_rule_key(name: str) -> Optional[str]:
    """Нормализует название правила из команды /запрет <название>"""
    clean = name.strip().lower()
    return RULE_NAME_ALIASES.get(clean)


def normalize_action(action: str) -> Optional[str]:
    """Нормализует введенное название действия"""
    clean = action.strip().lower()
    return ACTION_ALIASES.get(clean)


def format_action_display(action: str) -> str:
    """Форматирует действие для вывода в меню"""
    mapping = {
        "разрешено": "разрешено",
        "пред": "⚠️ пред",
        "мут": "🔇 мут",
        "кик": "❌ кик",
        "бан": "🚫 бан",
    }
    return mapping.get(action, action)


def get_effective_rule_action(rule_key: str, custom_rules: Dict[str, str]) -> str:
    """Возвращает текущее действие правила для чата (с учетом кастомных настроек или дефолта)"""
    if rule_key in custom_rules:
        return custom_rules[rule_key]
    rule_def = SECURITY_RULES.get(rule_key)
    return rule_def.default_action if rule_def else "разрешено"


def format_rules_menu(custom_rules: Dict[str, str]) -> str:
    """Генерирует форматированный текст текущих настроек запретов строго по ТЗ"""
    categories = ["Вложения", "Посты и ссылки", "Действия", "Нарушения"]
    sections = []

    for cat in categories:
        cat_lines = [f"{cat}:"]
        for key, r_def in SECURITY_RULES.items():
            if r_def.category != cat:
                continue
            act = get_effective_rule_action(key, custom_rules)
            act_display = format_action_display(act)
            cat_lines.append(f"{r_def.title}: {act_display} ({key})")
        sections.append("\n".join(cat_lines))

    header = "⚙️ Настройки запретов в беседе:\n"
    footer = (
        "\n\n💡 Чтобы изменить наказание, введите:\n"
        "«/запрет <название> <кик/мут/пред/бан/разрешено>»\n"
        "Пример: /запрет ссылка мут\n"
        "Или используйте кнопку «Настроить запреты» ниже."
    )
    return header + "\n\n".join(sections) + footer


def check_message_violations(
    message: Any,
    custom_rules: Dict[str, str],
    banwords: List[str]
) -> Optional[Tuple[str, str, str]]:
    """
    Проверяет входящее сообщение на нарушения активных правил.
    Возвращает (rule_key, action, reason) или None, если нарушений нет.
    """
    text = (getattr(message, "text", "") or "").strip()
    attachments = getattr(message, "attachments", []) or []
    action_event = getattr(message, "action", None)

    # 1. Проверка системных событий
    if action_event:
        act_type = getattr(action_event, "type", "") or getattr(action_event, "action", "")
        # Закреп
        if act_type in ("chat_pin_message",):
            act = get_effective_rule_action("закреп", custom_rules)
            if act != "разрешено":
                return ("закреп", act, "Закрепление сообщения запрещено")
        # Скриншот
        if act_type in ("chat_screenshot",):
            act = get_effective_rule_action("скрины", custom_rules)
            if act != "разрешено":
                return ("скрины", act, "Создание скриншотов запрещено")

    # Исчезающее сообщение (бомбочка)
    if getattr(message, "expire_ttl", None) or getattr(message, "is_expired", False):
        act = get_effective_rule_action("бомбочка", custom_rules)
        if act != "разрешено":
            return ("бомбочка", act, "Исчезающие сообщения запрещены")

    # 2. Проверка вложений
    for att in attachments:
        att_type = getattr(att, "type", None)
        if hasattr(att_type, "value"):
            att_type = att_type.value
        att_type = str(att_type or "").lower()

        # Фотография
        if att_type == "photo":
            act = get_effective_rule_action("фото", custom_rules)
            if act != "разрешено":
                return ("фото", act, "Отправка фотографий запрещена")

        # Видео
        elif att_type == "video":
            act = get_effective_rule_action("видео", custom_rules)
            if act != "разрешено":
                return ("видео", act, "Отправка видеозаписей запрещена")

        # Музыка
        elif att_type == "audio":
            act = get_effective_rule_action("аудио", custom_rules)
            if act != "разрешено":
                return ("аудио", act, "Отправка музыки запрещена")

        # Файлы / Документы / Гифки
        elif att_type == "doc":
            # Проверяем, не видеосообщение / граффити ли это
            doc_obj = getattr(att, "doc", None)
            doc_type = getattr(doc_obj, "type", 0) if doc_obj else 0
            if doc_type in (5, 6):  # 5 - аудио/видеосообщение, граффити
                act = get_effective_rule_action("кружочки", custom_rules)
                if act != "разрешено":
                    return ("кружочки", act, "Отправка видеосообщений/кружочков запрещена")
            else:
                act = get_effective_rule_action("файлы", custom_rules)
                if act != "разрешено":
                    return ("файлы", act, "Отправка файлов и gif запрещена")

        # Стикеры
        elif att_type == "sticker":
            act_sticker = get_effective_rule_action("стикеры", custom_rules)
            if act_sticker != "разрешено":
                return ("стикеры", act_sticker, "Отправка стикеров запрещена")

        # Голосовые сообщения (audio_message)
        elif att_type in ("audio_message",):
            act = get_effective_rule_action("гс", custom_rules)
            if act != "разрешено":
                return ("гс", act, "Голосовые сообщения запрещены")

        # Кружочки / граффити (graffiti, video_message)
        elif att_type in ("graffiti", "video_message"):
            act = get_effective_rule_action("кружочки", custom_rules)
            if act != "разрешено":
                return ("кружочки", act, "Отправка видеосообщений запрещена")

        # Опрос (poll)
        elif att_type == "poll":
            act = get_effective_rule_action("опрос", custom_rules)
            if act != "разрешено":
                return ("опрос", act, "Создание опросов запрещено")

        # История (story)
        elif att_type == "story":
            act = get_effective_rule_action("сторис", custom_rules)
            if act != "разрешено":
                return ("сторис", act, "Отправка историй запрещена")

        # Репост (wall)
        elif att_type == "wall":
            act = get_effective_rule_action("репост", custom_rules)
            if act != "разрешено":
                return ("репост", act, "Репосты записей со стены запрещены")

        # Комментарий к посту (wall_reply)
        elif att_type == "wall_reply":
            act = get_effective_rule_action("коммент", custom_rules)
            if act != "разрешено":
                return ("коммент", act, "Отправка комментариев к постам запрещена")

    # 3. Проверка текста сообщения
    if text:
        # Инвайт-ссылка на беседу
        if CHAT_INVITE_REGEX.search(text):
            act = get_effective_rule_action("инвайт", custom_rules)
            if act != "разрешено":
                return ("инвайт", act, "Ссылки на другие беседы запрещены")

        # Обычные ссылки
        if URL_REGEX.search(text):
            act = get_effective_rule_action("ссылка", custom_rules)
            if act != "разрешено":
                return ("ссылка", act, "Ссылки в сообщениях запрещены")

        # Упоминание сообществ
        if COMMUNITY_MENTION_REGEX.search(text):
            act = get_effective_rule_action("группа", custom_rules)
            if act != "разрешено":
                return ("группа", act, "Упоминание сообществ запрещено")

        # Пуш-упоминания (@all, @online)
        if PUSH_MENTION_REGEX.search(text):
            act = get_effective_rule_action("пуш", custom_rules)
            if act != "разрешено":
                return ("пуш", act, "Массовые упоминания (@all, @online) запрещены")

        # Банворды
        if banwords:
            text_lower = text.lower()
            for bw in banwords:
                if bw in text_lower:
                    act = get_effective_rule_action("банворд", custom_rules)
                    if act != "разрешено":
                        return ("банворд", act, f"Запрещенное слово в сообщении: {bw}")

        # Капс (длина текста >= 6, доля заглавных букв >= 70%)
        letters = [ch for ch in text if ch.isalpha()]
        if len(letters) >= 6:
            upper_count = sum(1 for ch in letters if ch.isupper())
            if (upper_count / len(letters)) >= 0.7:
                act = get_effective_rule_action("капс", custom_rules)
                if act != "разрешено":
                    return ("капс", act, "Использование капса запрещено")

        # Мат
        if MAT_REGEX.search(text):
            act = get_effective_rule_action("мат", custom_rules)
            if act != "разрешено":
                return ("мат", act, "Нецензурная лексика запрещена")

    return None
