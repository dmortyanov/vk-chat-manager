import os
import sys
import logging
import asyncio

# Гарантируем корректный вывод UTF-8 в консоли Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from vkbottle import Bot
from config import VK_TOKEN
from database import init_db
from middlewares import ModerationMiddleware
from handlers import labelers

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("ChatManager")


import socket

# Защита от одновременного запуска двух копий бота
_lock_socket = None


def acquire_single_instance_lock(port: int = 48192) -> bool:
    """Гарантирует, что запущен только один процесс бота"""
    global _lock_socket
    try:
        _lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        _lock_socket.bind(("127.0.0.1", port))
        _lock_socket.listen(1)
        return True
    except OSError:
        return False


def check_config():
    """Проверка наличия токена в .env и проверка единственности процесса"""
    if not acquire_single_instance_lock():
        logger.error(
            "\n"
            "=" * 60 + "\n"
            "⚠️ ВНИМАНИЕ: Другой экземпляр бота уже запущен!\n"
            "Одновременный запуск двух копий приводит к дублированию ответов\n"
            "и удвоенному подсчету статистики сообщений.\n"
            "Завершите предыдущий процесс перед повторным запуском.\n"
            "=" * 60
        )
        sys.exit(1)

    if not VK_TOKEN or VK_TOKEN == "vk1.a.your_token_here":
        logger.error(
            "\n"
            "=" * 60 + "\n"
            "❌ ОШИБКА: Токен сообщества ВКонтакте не найден!\n"
            "Пожалуйста, откройте файл .env и укажите ваш VK_TOKEN.\n"
            "Подробнее в файле README.md.\n"
            "=" * 60
        )
        sys.exit(1)


async def startup(bot: Bot):
    """Действия перед запуском LongPoll"""
    logger.info("Инициализация базы данных...")
    await init_db()
    logger.info("База данных готова к работе.")

    # Проверяем и включаем LongPoll в группе автоматически
    try:
        group_info = await bot.api.groups.get_by_id()
        if group_info.groups:
            group = group_info.groups[0]
            await bot.api.groups.set_long_poll_settings(
                group_id=group.id,
                enabled=True,
                api_version="5.199",
                message_new=True,
                message_reply=True,
                message_edit=True,
                message_event=True
            )
            logger.info(f"LongPoll API для группы «{group.name}» (ID {group.id}) успешно активирован.")
    except Exception as e:
        logger.warning(f"Не удалось обновить настройки LongPoll через API: {e}")

    # Проверка наличия файла фото-инструкции
    from config import INSTRUCTION_PHOTO_PATH
    if INSTRUCTION_PHOTO_PATH and os.path.isfile(INSTRUCTION_PHOTO_PATH):
        logger.info(f"Файл фото-инструкции найден: {INSTRUCTION_PHOTO_PATH}")
    else:
        logger.warning(f"Файл фото-инструкции НЕ найден по пути: {INSTRUCTION_PHOTO_PATH}")


def create_bot() -> Bot:
    """Сборка и настройка экземпляра бота"""
    check_config()
    bot = Bot(token=VK_TOKEN)

    # Включаем автоматическое удаление упоминания бота из начала текста в беседах
    bot.labeler.message_view.replace_mention = True

    # Регистрация middleware для контроля тишины, мутов и статистики
    bot.labeler.message_view.register_middleware(ModerationMiddleware)

    # Подключение всех модулей обработчиков (handlers)
    for custom_labeler in labelers:
        bot.labeler.load(custom_labeler)

    return bot


async def async_main():
    """Асинхронная точка входа"""
    bot = create_bot()
    await startup(bot)
    logger.info("Бот слушает события LongPoll. Готов к приему сообщений! 🚀")
    await bot.run_polling()


def main():
    print(
        r"""
  __      ___  __   ___        _     __  __                                 
  \ \    / / |/ /  / __|      | |   |  \/  |__ _ _ _  __ _ __ _ ___ _ _     
   \ \/\/ /| ' <  | (__   _   | |__ | |\/| / _` | ' \/ _` / _` / -_) '_|    
    \_/\_/ |_|\_\  \___| (_)  |____||_|  |_\__,_|_||_\__,_\__, \___|_|      
                                                          |___/             
        Чат-менеджер для ВКонтакте успешно запущен! 🚀
        """
    )
    try:
        asyncio.run(async_main())
    except (KeyboardInterrupt, SystemExit):
        print("\n🛑 Бот остановлен пользователем.")


if __name__ == "__main__":
    main()
