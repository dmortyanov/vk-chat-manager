import os
import sys
import asyncio
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Используем временную БД для тестов
TEST_DB_PATH = Path(__file__).resolve().parent / "test_features.db"
if TEST_DB_PATH.exists():
    TEST_DB_PATH.unlink()

os.environ["DATABASE_PATH"] = str(TEST_DB_PATH)

from config import Role
from database.db import init_db
from database.repository import Repository


async def run_tests():
    print("🧪 Запуск тестов мультибесед (/акик), правил, банвордов и очистки...")
    await init_db()

    # 1. Проверка названия роли
    assert Role.title(Role.OWNER) == "👑 Спец администратор"
    print("✅ Название роли Спец администратор: OK")

    # 2. Проверка изоляции мультибесед для /акик (через систему связывания)
    # Павел (id 100) владеет беседами 2000000001 и 2000000002
    await Repository.get_or_create_chat(2000000001, owner_id=100)
    await Repository.set_chat_owner(2000000001, 100)

    await Repository.get_or_create_chat(2000000002, owner_id=100)
    await Repository.set_chat_owner(2000000002, 100)

    # Иван (id 200) владеет беседой 2000000003
    await Repository.get_or_create_chat(2000000003, owner_id=200)
    await Repository.set_chat_owner(2000000003, 200)

    # До явной привязки — get_owner_chats возвращает пустой список
    pavel_chats_before = await Repository.get_owner_chats(100)
    assert len(pavel_chats_before) == 0, f"До привязки у Павла не должно быть связанных чатов: {pavel_chats_before}"
    print("✅ До привязки: get_owner_chats возвращает пустой список: OK")

    # Явная привязка бесед через link_chat
    assert await Repository.link_chat(100, 2000000001) == True
    assert await Repository.link_chat(100, 2000000002) == True
    assert await Repository.link_chat(200, 2000000003) == True

    # Повторная привязка возвращает False
    assert await Repository.link_chat(100, 2000000001) == False
    print("✅ Повторная привязка возвращает False: OK")

    pavel_chats = await Repository.get_owner_chats(100)
    ivan_chats = await Repository.get_owner_chats(200)

    assert set(pavel_chats) == {2000000001, 2000000002}, f"Чаты Павла: {pavel_chats}"
    assert set(ivan_chats) == {2000000003}, f"Чаты Ивана: {ivan_chats}"
    print("✅ Изоляция бесед для команды /акик через /связать (Павел не затрагивает беседы Ивана): OK")

    # Проверка get_linked_chats
    linked = await Repository.get_linked_chats(100)
    assert set(linked) == {2000000001, 2000000002}
    print("✅ get_linked_chats: OK")

    # Проверка is_chat_linked
    assert await Repository.is_chat_linked(100, 2000000001) == True
    assert await Repository.is_chat_linked(100, 2000000003) == False
    assert await Repository.is_chat_linked(200, 2000000003) == True
    print("✅ is_chat_linked: OK")

    # Отвязка одной беседы
    assert await Repository.unlink_chat(100, 2000000002) == True
    remaining = await Repository.get_linked_chats(100)
    assert set(remaining) == {2000000001}
    assert await Repository.unlink_chat(100, 2000000002) == False  # уже отвязана
    print("✅ unlink_chat: OK")

    # Восстановим для дальнейших тестов
    await Repository.link_chat(100, 2000000002)

    # 3. Настройка матрицы запретов в БД
    await Repository.set_chat_rule(2000000001, "ссылка", "мут")
    await Repository.set_chat_rule(2000000001, "инвайт", "бан")
    rules = await Repository.get_chat_rules(2000000001)
    assert rules.get("ссылка") == "мут"
    assert rules.get("инвайт") == "бан"

    # В беседе 2000000002 правил нет
    rules_2 = await Repository.get_chat_rules(2000000002)
    assert len(rules_2) == 0
    print("✅ Хранение правил запретов для каждого чата: OK")

    # 4. Банворды (запрещенные слова)
    await Repository.add_banword(2000000001, "казино")
    await Repository.add_banword(2000000001, "спам")
    bw = await Repository.get_banwords(2000000001)
    assert set(bw) == {"казино", "спам"}

    await Repository.remove_banword(2000000001, "спам")
    bw_after = await Repository.get_banwords(2000000001)
    assert set(bw_after) == {"казино"}
    print("✅ Система банвордов (добавление, список, удаление): OK")

    # 5. Сохранение сообщений и получение для кнопки 'Очистить'
    boris_id = 555
    await Repository.save_message_cmid(2000000001, boris_id, 101)
    await Repository.save_message_cmid(2000000001, boris_id, 102)
    await Repository.save_message_cmid(2000000001, boris_id, 103)

    cmids = await Repository.get_user_cmids(2000000001, boris_id)
    assert set(cmids) == {101, 102, 103}

    await Repository.delete_user_cmids(2000000001, boris_id)
    cmids_empty = await Repository.get_user_cmids(2000000001, boris_id)
    assert len(cmids_empty) == 0
    print("✅ Буферизация и очистка сообщений пользователя (для кнопки 'Очистить'): OK")

    # 6. Проверка лимита символов в сообщении
    default_len = await Repository.get_max_message_length(2000000001)
    assert default_len == 500
    await Repository.set_max_message_length(2000000001, 250)
    updated_len = await Repository.get_max_message_length(2000000001)
    assert updated_len == 250
    print("✅ Хранение и обновление лимита символов в БД: OK")

    # Очистка тестовой БД
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()

    print("\n🎉 Все тесты нового функционала успешно пройдены!")


if __name__ == "__main__":
    asyncio.run(run_tests())
