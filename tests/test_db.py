import os
import time
import asyncio
import tempfile
from pathlib import Path
import sys

# Настройка UTF-8 вывода в Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Добавляем корневую директорию проекта в sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Устанавливаем тестовую базу данных во временный файл
test_db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
test_db_path = test_db_file.name
test_db_file.close()

os.environ["DATABASE_PATH"] = test_db_path

from config import Role
from database.db import init_db
from database.repository import Repository


async def run_tests():
    print("🧪 Запуск тестов базы данных...")
    await init_db()

    peer_id = 2000000001
    owner_id = 100
    admin_id = 200
    moder_id = 300
    user_id = 400

    # 1. Тест создания чата и установки владельца
    await Repository.set_chat_owner(peer_id, owner_id)
    chat = await Repository.get_chat(peer_id)
    assert chat is not None, "Чат должен быть создан"
    assert chat["owner_id"] == owner_id, "Владелец должен совпадать"

    owner_role = await Repository.get_member_role(peer_id, owner_id)
    assert owner_role == Role.OWNER, f"Роль создателя должна быть OWNER, получено {owner_role}"
    print("✅ Создание чата и владелец: OK")

    # 2. Тест назначения и снятия ролей
    await Repository.set_member_role(peer_id, admin_id, Role.ADMIN)
    await Repository.set_member_role(peer_id, moder_id, Role.MODERATOR)
    await Repository.set_member_role(peer_id, user_id, Role.USER)

    assert await Repository.get_member_role(peer_id, admin_id) == Role.ADMIN
    assert await Repository.get_member_role(peer_id, moder_id) == Role.MODERATOR
    assert await Repository.get_member_role(peer_id, user_id) == Role.USER
    assert await Repository.get_members_by_role(peer_id, Role.ADMIN) == [admin_id]
    assert await Repository.get_members_by_role(peer_id, Role.MODERATOR) == [moder_id]
    print("✅ Назначение ролей и списки по ролям: OK")

    # 3. Тест статистики сообщений
    await Repository.increment_messages(peer_id, user_id)
    await Repository.increment_messages(peer_id, user_id)
    stats = await Repository.get_member_stats(peer_id, user_id)
    assert stats["messages_count"] == 2, f"Сообщений должно быть 2, получено {stats['messages_count']}"
    print("✅ Статистика сообщений: OK")

    # 4. Тест варнов (выдача, лимит, снятие)
    w1 = await Repository.add_warn(peer_id, user_id, moder_id, "Спам")
    assert w1 == 1, f"Варн должен быть 1, получено {w1}"

    w2 = await Repository.add_warn(peer_id, user_id, moder_id, "Мат")
    assert w2 == 2, f"Варнов должно быть 2, получено {w2}"

    warned_list = await Repository.get_chat_warned_users(peer_id)
    assert len(warned_list) == 1
    assert warned_list[0]["user_id"] == user_id

    w_removed = await Repository.remove_warn(peer_id, user_id)
    assert w_removed == 1, f"После снятия должен остаться 1 варн, получено {w_removed}"

    await Repository.reset_warns(peer_id, user_id)
    assert (await Repository.get_or_create_member(peer_id, user_id))["warns_count"] == 0
    print("✅ Система предупреждений (варны): OK")

    # 5. Тест мута
    future_time = int(time.time()) + 300
    await Repository.set_mute(peer_id, user_id, future_time)
    assert await Repository.is_muted(peer_id, user_id) is True, "Пользователь должен быть в муте"

    await Repository.remove_mute(peer_id, user_id)
    assert await Repository.is_muted(peer_id, user_id) is False, "Мут должен быть снят"

    # Истекший мут
    past_time = int(time.time()) - 10
    await Repository.set_mute(peer_id, user_id, past_time)
    assert await Repository.is_muted(peer_id, user_id) is False, "Истекший мут должен автоматически очищаться"
    print("✅ Система заглушек (мут): OK")

    # 6. Тест банов
    await Repository.add_ban(peer_id, user_id, admin_id, "Оскорбления")
    ban = await Repository.get_ban(peer_id, user_id)
    assert ban is not None, "Бан должен быть найден"
    assert ban["reason"] == "Оскорбления"

    banlist = await Repository.get_banlist(peer_id)
    assert len(banlist) == 1
    assert banlist[0]["user_id"] == user_id

    unbanned = await Repository.remove_ban(peer_id, user_id)
    assert unbanned is True, "Разбан должен вернуть True"
    assert await Repository.get_ban(peer_id, user_id) is None
    print("✅ Система банов (ban/unban/banlist): OK")

    # 7. Тест режима тишины
    await Repository.set_silence(peer_id, True)
    chat_silence = await Repository.get_chat(peer_id)
    assert chat_silence["silence_mode"] == 1
    await Repository.set_silence(peer_id, False)
    chat_silence = await Repository.get_chat(peer_id)
    assert chat_silence["silence_mode"] == 0
    print("✅ Режим тишины: OK")

    # 8. Тест приветствия
    await Repository.set_welcome(peer_id, "Привет, {user} в {chat}!", True)
    chat_w = await Repository.get_chat(peer_id)
    assert chat_w["welcome_text"] == "Привет, {user} в {chat}!"
    assert chat_w["welcome_enabled"] == 1
    print("✅ Настройки приветствия: OK")

    # 9. Тест получения всех бесед для рассылки
    all_chats = await Repository.get_all_chat_ids()
    assert peer_id in all_chats, "Созданная беседа должна присутствовать в списке всех чатов"
    print("✅ Получение списка бесед для рассылки: OK")

    print("\n🎉 Все тесты базы данных успешно пройдены!")

    # Удаляем временную БД
    try:
        os.remove(test_db_path)
    except Exception:
        pass


if __name__ == "__main__":
    asyncio.run(run_tests())
