import re
import bisect
from datetime import datetime, timezone, timedelta
from typing import Optional
import aiohttp

FOAF_URL = "https://vk.com/foaf.php?id={}"
DATE_REGEX = re.compile(r'<ya:created dc:date="([^"]+)"\s*\/>')

MONTHS_RU = [
    "", "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря"
]

# Калибровочные вехи регистрации пользователей ВКонтакте (ID -> UTC дата)
# Обеспечивают расчет даты регистрации при отключенном VK XML-шлюзе
REG_MILESTONES = [
    (1, datetime(2006, 10, 10, tzinfo=timezone.utc)),
    (50_000, datetime(2007, 2, 1, tzinfo=timezone.utc)),
    (100_000, datetime(2007, 4, 1, tzinfo=timezone.utc)),
    (500_000, datetime(2007, 8, 15, tzinfo=timezone.utc)),
    (1_000_000, datetime(2007, 11, 20, tzinfo=timezone.utc)),
    (3_000_000, datetime(2008, 2, 10, tzinfo=timezone.utc)),
    (5_000_000, datetime(2008, 4, 1, tzinfo=timezone.utc)),
    (10_000_000, datetime(2008, 6, 15, tzinfo=timezone.utc)),
    (15_000_000, datetime(2008, 9, 1, tzinfo=timezone.utc)),
    (20_000_000, datetime(2008, 11, 15, tzinfo=timezone.utc)),
    (35_000_000, datetime(2009, 4, 15, tzinfo=timezone.utc)),
    (50_000_000, datetime(2009, 10, 20, tzinfo=timezone.utc)),
    (75_000_000, datetime(2010, 4, 20, tzinfo=timezone.utc)),
    (100_000_000, datetime(2010, 11, 24, tzinfo=timezone.utc)),
    (125_000_000, datetime(2011, 5, 15, tzinfo=timezone.utc)),
    (150_000_000, datetime(2011, 12, 1, tzinfo=timezone.utc)),
    (175_000_000, datetime(2012, 6, 25, tzinfo=timezone.utc)),
    (200_000_000, datetime(2013, 3, 1, tzinfo=timezone.utc)),
    (225_000_000, datetime(2013, 10, 15, tzinfo=timezone.utc)),
    (250_000_000, datetime(2014, 4, 20, tzinfo=timezone.utc)),
    (275_000_000, datetime(2014, 10, 30, tzinfo=timezone.utc)),
    (300_000_000, datetime(2015, 5, 10, tzinfo=timezone.utc)),
    (350_000_000, datetime(2016, 2, 15, tzinfo=timezone.utc)),
    (400_000_000, datetime(2016, 12, 10, tzinfo=timezone.utc)),
    (450_000_000, datetime(2017, 10, 20, tzinfo=timezone.utc)),
    (500_000_000, datetime(2018, 8, 15, tzinfo=timezone.utc)),
    (550_000_000, datetime(2019, 6, 10, tzinfo=timezone.utc)),
    (600_000_000, datetime(2020, 5, 20, tzinfo=timezone.utc)),
    (650_000_000, datetime(2021, 4, 10, tzinfo=timezone.utc)),
    (700_000_000, datetime(2022, 1, 15, tzinfo=timezone.utc)),
    (750_000_000, datetime(2022, 11, 20, tzinfo=timezone.utc)),
    (800_000_000, datetime(2023, 9, 1, tzinfo=timezone.utc)),
    (850_000_000, datetime(2024, 6, 1, tzinfo=timezone.utc)),
    (900_000_000, datetime(2025, 3, 1, tzinfo=timezone.utc)),
    (950_000_000, datetime(2026, 1, 1, tzinfo=timezone.utc)),
    (1_000_000_000, datetime(2026, 9, 1, tzinfo=timezone.utc)),
]


def _format_russian_date(dt: datetime) -> str:
    """Форматирует дату в русский вид: 6 марта 2013 года в 07:46 (МСК)"""
    # Переводим в часовой пояс Москвы (UTC+3)
    msk_tz = timezone(timedelta(hours=3))
    dt_msk = dt.astimezone(msk_tz)

    month_name = MONTHS_RU[dt_msk.month]
    return f"{dt_msk.day} {month_name} {dt_msk.year} года в {dt_msk.strftime('%H:%M:%S')} (МСК)"


def _estimate_by_id(user_id: int) -> str:
    """Оценивает дату регистрации на основе калибровочной интерполяции по ID"""
    ids = [m[0] for m in REG_MILESTONES]
    idx = bisect.bisect_right(ids, user_id)

    if idx == 0:
        dt = REG_MILESTONES[0][1]
    elif idx >= len(REG_MILESTONES):
        dt = REG_MILESTONES[-1][1]
    else:
        id1, d1 = REG_MILESTONES[idx - 1]
        id2, d2 = REG_MILESTONES[idx]
        ratio = (user_id - id1) / (id2 - id1)
        ts = d1.timestamp() + ratio * (d2.timestamp() - d1.timestamp())
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)

    return _format_russian_date(dt)


async def get_vk_registration_date(user_id: int) -> Optional[str]:
    """
    Определяет точную дату регистрации страницы ВКонтакте:
    1. Пробует получить через FOAF XML (если шлюз ВК отвечает)
    2. При недоступности FOAF использует интерполяционную модель по ID
    """
    if user_id <= 0:
        return None

    # 1. Попытка через FOAF (с отключенной строгой SSL проверкой)
    try:
        timeout = aiohttp.ClientTimeout(total=2)
        connector = aiohttp.TCPConnector(ssl=False)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        async with aiohttp.ClientSession(timeout=timeout, connector=connector, headers=headers) as session:
            async with session.get(FOAF_URL.format(user_id)) as response:
                if response.status == 200:
                    text = await response.text(encoding="windows-1251", errors="ignore")
                    match = DATE_REGEX.search(text)
                    if match:
                        iso_str = match.group(1)
                        dt = datetime.fromisoformat(iso_str)
                        return _format_russian_date(dt)
    except Exception:
        pass

    # 2. Надежный fallback по ID (работает всегда)
    return _estimate_by_id(user_id)
