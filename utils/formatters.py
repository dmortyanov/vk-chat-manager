from datetime import datetime, timezone, timedelta
from typing import Tuple, Optional, Any
from vkbottle import ABCAPI

MSK_TZ = timezone(timedelta(hours=3))


def plural_ru(n: int, forms: Tuple[str, str, str]) -> str:
    """
    Склонение русских слов:
    plural_ru(count, ('предупреждение', 'предупреждения', 'предупреждений'))
    """
    n = abs(n) % 100
    n1 = n % 10
    if 10 < n < 20:
        return forms[2]
    if 1 < n1 < 5:
        return forms[1]
    if n1 == 1:
        return forms[0]
    return forms[2]


async def get_user_mention(user_id: int, api: ABCAPI, fallback_name: Optional[str] = None) -> str:
    """
    Возвращает кликабельное упоминание пользователя: [id123|Имя Фамилия].
    Если это сообщество/бот, возвращает [club123|Название].
    """
    if user_id > 0:
        try:
            users = await api.users.get(user_ids=[user_id])
            if users:
                u = users[0]
                return f"[id{user_id}|{u.first_name} {u.last_name}]"
        except Exception:
            pass
        return f"[id{user_id}|{fallback_name or f'Пользователь #{user_id}'}]"
    else:
        group_id = abs(user_id)
        try:
            groups = await api.groups.get_by_id(group_id=str(group_id))
            if groups:
                g = groups[0]
                return f"[club{group_id}|{g.name}]"
        except Exception:
            pass
        return f"[club{group_id}|{fallback_name or f'Сообщество #{group_id}'}]"


def format_duration(minutes: int) -> str:
    """Форматирует количество минут в читаемый вид (часы/минуты)"""
    if minutes < 60:
        return f"{minutes} {plural_ru(minutes, ('минуту', 'минуты', 'минут'))}"
    hours = minutes // 60
    rem_min = minutes % 60
    h_str = f"{hours} {plural_ru(hours, ('час', 'часа', 'часов'))}"
    if rem_min > 0:
        return f"{h_str} {rem_min} {plural_ru(rem_min, ('минуту', 'минуты', 'минут'))}"
    return h_str


def format_msk_datetime(dt_val: Any) -> str:
    """
    Преобразует дату/время из БД (UTC) в удобный московский формат:
    '11.09.2026 в 18:25:57 (МСК)'
    """
    if not dt_val:
        return "Неизвестно"

    if isinstance(dt_val, (int, float)):
        dt = datetime.fromtimestamp(dt_val, tz=MSK_TZ)
        return dt.strftime("%d.%m.%Y в %H:%M:%S (МСК)")

    try:
        dt_str = str(dt_val).replace(" ", "T")
        dt = datetime.fromisoformat(dt_str)
        if dt.tzinfo is None:
            # SQLite CURRENT_TIMESTAMP сохраняет время в UTC
            dt = dt.replace(tzinfo=timezone.utc)
        dt_msk = dt.astimezone(MSK_TZ)
        return dt_msk.strftime("%d.%m.%Y в %H:%M:%S (МСК)")
    except Exception:
        return str(dt_val)
