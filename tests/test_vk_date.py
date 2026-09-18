import sys
from pathlib import Path
from datetime import datetime
import re

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.vk_date import DATE_REGEX, MONTHS_RU


def run_vk_date_tests():
    print("🧪 Запуск тестов модуля vk_date...")

    mock_foaf_xml = """<?xml version="1.0" encoding="windows-1251"?>
<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
         xmlns:rdfs="http://www.w3.org/2000/01/rdf-schema#"
         xmlns:ya="http://blogs.yandex.ru/schema/foaf/"
         xmlns:foaf="http://xmlns.com/foaf/0.1/"
         xmlns:dc="http://purl.org/dc/elements/1.1/">
<foaf:Person>
    <ya:created dc:date="2006-09-23T21:41:20+04:00" />
    <foaf:name>Павел Дуров</foaf:name>
</foaf:Person>
</rdf:RDF>"""

    match = DATE_REGEX.search(mock_foaf_xml)
    assert match is not None, "Регулярное выражение должно найти дату"
    iso_date = match.group(1)
    assert iso_date == "2006-09-23T21:41:20+04:00"

    dt = datetime.fromisoformat(iso_date)
    month_name = MONTHS_RU[dt.month]
    formatted = f"{dt.day} {month_name} {dt.year} года в {dt.strftime('%H:%M:%S')}"

    assert formatted == "23 сентября 2006 года в 21:41:20", f"Получено: {formatted}"
    print(f"✅ Парсинг даты регистрации FOAF: {formatted} — OK")

    # Тест калибровочной интерполяции по ID
    from utils.vk_date import _estimate_by_id
    est_date = _estimate_by_id(200000000)
    assert "2013" in est_date and "марта" in est_date, f"Получено: {est_date}"
    print(f"✅ Оценка даты регистрации по ID (fallback): {est_date} — OK")

    print("\n🎉 Все тесты vk_date успешно пройдены!")


if __name__ == "__main__":
    run_vk_date_tests()
