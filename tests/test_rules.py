import sys
from pathlib import Path
import asyncio

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.rules import CommandRule


class MockEvent:
    def __init__(self, text: str):
        self.text = text


async def test_command_rule():
    print("🧪 Тестирование CommandRule на строгие префиксы и защиту от слова 'бот'...")

    tut_rule = CommandRule(["тут", "ping"], prefixes=("/",))
    start_rule = CommandRule(["start", "старт"], prefixes=("/",))
    kick_rule = CommandRule(["kick", "кик"], prefixes=("/",))
    warnlist_rule = CommandRule(["warnings in the chat", "варнлист"], prefixes=("/",))
    broadcast_rule = CommandRule(["рассылка", "broadcast"], prefixes=("/",))
    plus_admin_rule = CommandRule(["+admin", "+админ"], prefixes=("", "/"))
    minus_admin_rule = CommandRule(["-admin", "-админ"], prefixes=("", "/"))
    plus_moder_rule = CommandRule(["+moder", "+модер", "+moders", "moder", "модер", "moders"], prefixes=("", "/"))
    minus_moder_rule = CommandRule(["-moder", "-модер", "-moders", "unmoder", "размодер"], prefixes=("", "/"))
    ban_rule = CommandRule(["ban", "бан"], prefixes=("/",))
    unban_rule = CommandRule(["unban", "разбан"], prefixes=("/",))
    warn_rule = CommandRule(["warn", "варн"], prefixes=("/",))
    unwarn_rule = CommandRule(["unwarn", "анварн", "снятьварн"], prefixes=("/",))
    admins_rule = CommandRule(["админы", "администраторы", "admins", "administrators"], prefixes=("/",))
    moderators_rule = CommandRule(["модераторы", "модеры", "moders", "moderators"], prefixes=("/",))

    # 1. Проверяем, что обычное слово "бот" и фразы с "бот" НЕ срабатывают нигде
    assert not await tut_rule.check(MockEvent("бот")), "Слово 'бот' не должно вызывать команду!"
    assert not await tut_rule.check(MockEvent("бот тут")), "'бот тут' без префикса не должно вызывать команду!"
    assert not await tut_rule.check(MockEvent("бот которого ты просил")), "'бот которого ты просил' не должно срабатывать!"
    assert not await start_rule.check(MockEvent("бот")), "'бот' не должен вызывать /start"
    assert not await kick_rule.check(MockEvent("бот")), "'бот' не должен вызывать /kick"
    print("✅ Слово 'бот' и фразы с ним успешно отвергаются всеми правилами")

    # 2. Проверяем, что команды без префиксов отвергаются
    assert not await tut_rule.check(MockEvent("тут")), "Обычное слово 'тут' без слэша не должно срабатывать"
    assert not await start_rule.check(MockEvent("старт")), "Обычное слово 'старт' без слэша не должно срабатывать"
    assert not await kick_rule.check(MockEvent("кик @user")), "Обычное слово 'кик' без слэша не должно срабатывать"
    assert not await broadcast_rule.check(MockEvent("рассылка Привет")), "Обычное слово 'рассылка' без слэша не должно срабатывать"
    assert not await ban_rule.check(MockEvent("бан @user")), "Обычное слово 'бан' без слэша/+ не должно срабатывать"
    assert not await warn_rule.check(MockEvent("варн @user")), "Обычное слово 'варн' без слэша/+ не должно срабатывать"
    assert not await admins_rule.check(MockEvent("админы")), "Обычное слово 'админы' без слэша не должно срабатывать"
    assert not await moderators_rule.check(MockEvent("модераторы")), "Обычное слово 'модераторы' без слэша не должно срабатывать"
    print("✅ Текстовые команды без префикса '/' или '+' отвергаются")

    # 3. Проверяем корректную работу со слэшем
    assert await tut_rule.check(MockEvent("/тут")), "Команда /тут должна срабатывать"
    assert await tut_rule.check(MockEvent("/ping")), "Команда /ping должна срабатывать"
    assert await start_rule.check(MockEvent("/start")), "Команда /start должна срабатывать"
    assert await kick_rule.check(MockEvent("/kick @user")), "Команда /kick @user должна срабатывать"
    assert await warnlist_rule.check(MockEvent("/warnings in the chat")), "Составная команда должна срабатывать"
    assert await broadcast_rule.check(MockEvent("/рассылка Внимание всем!")), "Команда /рассылка должна срабатывать"
    assert await broadcast_rule.check(MockEvent("/broadcast Update")), "Команда /broadcast должна срабатывать"
    assert await ban_rule.check(MockEvent("/ban @user")), "Команда /ban должна срабатывать"
    assert await ban_rule.check(MockEvent("/бан @user")), "Команда /бан должна срабатывать"
    assert await unban_rule.check(MockEvent("/unban @user")), "Команда /unban должна срабатывать"
    assert await unban_rule.check(MockEvent("/разбан @user")), "Команда /разбан должна срабатывать"
    assert await warn_rule.check(MockEvent("/warn @user")), "Команда /warn должна срабатывать"
    assert await warn_rule.check(MockEvent("/варн @user")), "Команда /варн должна срабатывать"
    assert await unwarn_rule.check(MockEvent("/unwarn @user")), "Команда /unwarn должна срабатывать"
    assert await unwarn_rule.check(MockEvent("/анварн @user")), "Команда /анварн должна срабатывать"
    assert await admins_rule.check(MockEvent("/админы")), "Команда /админы должна срабатывать"
    assert await admins_rule.check(MockEvent("/admins")), "Команда /admins должна срабатывать"
    assert await moderators_rule.check(MockEvent("/модераторы")), "Команда /модераторы должна срабатывать"
    assert await moderators_rule.check(MockEvent("/модеры")), "Команда /модеры должна срабатывать"
    assert await moderators_rule.check(MockEvent("/moders")), "Команда /moders должна срабатывать"
    print("✅ Команды с префиксом '/' корректно распознаются")

    # 4. Проверяем команды с '+' и '-'
    assert await plus_admin_rule.check(MockEvent("+admin @user")), "+admin @user должна срабатывать"
    assert await minus_admin_rule.check(MockEvent("-admin @user")), "-admin @user должна срабатывать"
    assert await plus_moder_rule.check(MockEvent("+moder @user")), "+moder @user должна срабатывать"
    assert await plus_moder_rule.check(MockEvent("+модер @user")), "+модер @user должна срабатывать"
    assert await plus_moder_rule.check(MockEvent("+moders @user")), "+moders @user должна срабатывать"
    assert await minus_moder_rule.check(MockEvent("-moder @user")), "-moder @user должна срабатывать"
    assert await minus_moder_rule.check(MockEvent("-модер @user")), "-модер @user должна срабатывать"
    assert await minus_moder_rule.check(MockEvent("-moders @user")), "-moders @user должна срабатывать"
    assert not await ban_rule.check(MockEvent("+ban @user")), "+ban не должно срабатывать (только /ban)"
    assert not await ban_rule.check(MockEvent("+бан @user")), "+бан не должно срабатывать (только /бан)"
    assert not await unban_rule.check(MockEvent("-ban @user")), "-ban не должно срабатывать (только /unban)"
    assert not await unban_rule.check(MockEvent("-бан @user")), "-бан не должно срабатывать (только /разбан)"
    assert not await warn_rule.check(MockEvent("+warn @user")), "+warn не должно срабатывать (только /warn)"
    assert not await warn_rule.check(MockEvent("+варн @user")), "+варн не должно срабатывать (только /варн)"
    assert not await unwarn_rule.check(MockEvent("-warn @user")), "-warn не должно срабатывать (только /unwarn)"
    assert not await unwarn_rule.check(MockEvent("-варн @user")), "-варн не должно срабатывать (только /анварн)"
    print("✅ Команды с префиксами '+' и '-' корректно распознаются")

    # 5. Проверяем упоминания бота [club123|Бот]
    assert await tut_rule.check(MockEvent("[club123456789|@bot] /тут")), "Упоминание бота со слэшем должно срабатывать"
    assert not await tut_rule.check(MockEvent("[club123456789|@bot] бот")), "Упоминание бота со словом 'бот' НЕ должно срабатывать"
    assert not await tut_rule.check(MockEvent("[club123456789|@bot] привет")), "Упоминание бота с обычным текстом НЕ должно срабатывать"
    assert await plus_admin_rule.check(MockEvent("[club123456789|@bot] +admin @user")), "Упоминание бота с +admin должно срабатывать"
    print("✅ Упоминания сообщества [club...|...] корректно обрабатываются")

    print("\n🎉 Все тесты правил команд пройдены на 100%!")


if __name__ == "__main__":
    asyncio.run(test_command_rule())
