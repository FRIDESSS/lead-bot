import asyncio
import json
import logging
import os

import aiohttp
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode, ContentType
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

# === НАСТРОЙКИ (через переменные окружения) ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
MAKE_WEBHOOK = os.getenv("MAKE_WEBHOOK")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
MANAGER_USERNAME = os.getenv("MANAGER_USERNAME", "Psycho_tipe")
FREE_GUIDE_LINK = os.getenv("FREE_GUIDE_LINK", "https://t.me/")

MANAGER_LINK = "https://t.me/" + MANAGER_USERNAME
MAIN_PRODUCT_LINK = MANAGER_LINK

# === ФАЙЛ ДЛЯ БЭКАПА ===
BACKUP_FILE = "users_backup.json"

# === ЛОГИ ===
logging.basicConfig(level=logging.INFO)

# === БОТ + ДИСПЕТЧЕР ===
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())
router = Router()
dp.include_router(router)

# === СОСТОЯНИЯ ===
class Survey(StatesGroup):
    name = State()
    age = State()
    goal = State()
    source = State()

# === ХРАНИЛИЩЕ ===
completed_users = set()
watched_guide = set()
total_leads = 0

# === ЗАГРУЗКА БЭКАПА ===
def load_backup():
    global completed_users, watched_guide, total_leads
    try:
        with open(BACKUP_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            completed_users = set(data.get("completed_users", []))
            watched_guide = set(data.get("watched_guide", []))
            total_leads = data.get("total_leads", 0)
    except FileNotFoundError:
        pass

def save_backup():
    data = {
        "completed_users": list(completed_users),
        "watched_guide": list(watched_guide),
        "total_leads": total_leads
    }
    with open(BACKUP_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

load_backup()

# === ОТПРАВКА В MAKE.COM ===
async def send_to_make(data: dict):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(MAKE_WEBHOOK, json=data, timeout=10) as resp:
                return resp.status == 200
    except Exception:
        return False

# === ПРИВЕТСТВИЕ ===
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    user_id = message.from_user.id
    await state.clear()

    if user_id in completed_users:
        await message.answer(
            "👋 Привет снова!\n\n"
            "Ты уже проходил(а) опрос. Вот твой гайд:",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="👉 Открыть гайд", url=FREE_GUIDE_LINK)],
                [InlineKeyboardButton(text="✅ Посмотрел", callback_data="watched")]
            ])
        )
        return

    await state.set_state(Survey.name)
    await message.answer(
        "👋 Привет! Рад тебя видеть.\n\n"
        "🎁 У меня для тебя есть кое-что полезное — <b>бесплатный гайд</b>, "
        "который поможет сделать первый шаг.\n\n"
        "Чтобы получить доступ, пройди небольшой мини-опрос (всего 4 вопроса). "
        "Это займёт буквально минуту.\n\n"
        "Готов(а)? Тогда поехали! 🚀"
    )
    await message.answer("Как тебя зовут?")

# === ВОПРОС 1: ИМЯ ===
@router.message(Survey.name)
async def process_name(message: Message, state: FSMContext):
    if message.content_type != ContentType.TEXT:
        await message.answer("⚠️ Пожалуйста, напиши ответ текстом.\n\nКак тебя зовут?")
        return
    await state.update_data(name=message.text)
    await state.set_state(Survey.age)
    await message.answer("Сколько тебе лет?")

# === ВОПРОС 2: ВОЗРАСТ ===
@router.message(Survey.age)
async def process_age(message: Message, state: FSMContext):
    if message.content_type != ContentType.TEXT:
        await message.answer("⚠️ Пожалуйста, напиши ответ текстом.\n\nСколько тебе лет?")
        return
    try:
        age = int(message.text.strip())
    except ValueError:
        await message.answer("⚠️ Пожалуйста, укажи возраст числом.\n\nНапример: 25")
        return
    await state.update_data(age=age)
    await state.set_state(Survey.goal)
    await message.answer("Какая у тебя цель?")

# === ВОПРОС 3: ЦЕЛЬ ===
@router.message(Survey.goal)
async def process_goal(message: Message, state: FSMContext):
    if message.content_type != ContentType.TEXT:
        await message.answer("⚠️ Пожалуйста, напиши ответ текстом.\n\nКакая у тебя цель?")
        return
    await state.update_data(goal=message.text)
    await state.set_state(Survey.source)
    await message.answer("Откуда ты узнал(а) обо мне?")

# === ВОПРОС 4: ИСТОЧНИК ===
@router.message(Survey.source)
async def process_source(message: Message, state: FSMContext):
    if message.content_type != ContentType.TEXT:
        await message.answer("⚠️ Пожалуйста, напиши ответ текстом.\n\nОткуда ты узнал(а) обо мне?")
        return

    data = await state.get_data()
    data["source"] = message.text
    data["user_id"] = message.from_user.id
    data["username"] = message.from_user.username or "None"
    data["utm"] = "direct"

    completed_users.add(message.from_user.id)
    save_backup()

    success = await send_to_make(data)
    if success:
        global total_leads
        total_leads += 1
        save_backup()

    await state.clear()

    await message.answer(
        "🔥 Спасибо за ответы! Вот твой гайд:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="👉 Открыть гайд", url=FREE_GUIDE_LINK)],
            [InlineKeyboardButton(text="✅ Посмотрел", callback_data="watched")]
        ])
    )

# === КНОПКА "ПОСМОТРЕЛ" ===
@router.callback_query(F.data == "watched")
async def watched_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    watched_guide.add(user_id)
    save_backup()

    await callback.message.answer(
        "🔥 Круто, что посмотрел!\n\n"
        "Если хочешь <b>глубже разобраться в теме</b> и получить пошаговую методику — "
        "приглашаю на <b>основной курс</b>.\n\n"
        "Что включено:\n"
        "✅ Пошаговая методика\n"
        "✅ Практические задания\n"
        "✅ Поддержка и обратная связь\n\n"
        "Готов присоединиться? 👇",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔥 Узнать о курсе", url=MAIN_PRODUCT_LINK)],
            [InlineKeyboardButton(text="💬 Написать менеджеру", url=MANAGER_LINK)]
        ])
    )
    await callback.answer()

# === КОМАНДА /RESET (только для админа) ===
@router.message(Command("reset"))
async def cmd_reset(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    user_id = message.from_user.id
    if user_id in completed_users:
        completed_users.discard(user_id)
        watched_guide.discard(user_id)
        save_backup()
        await message.answer("✅ Твои данные сброшены. Напиши /start, чтобы пройти опрос заново.")
    else:
        await message.answer("Ты ещё не проходил опрос.")

# === КОМАНДА /STATS (только для админа) ===
@router.message(Command("stats"))
async def cmd_stats(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    total = len(completed_users)
    watched = len(watched_guide)
    conv_guide = round(watched / total * 100, 1) if total else 0

    text = (
        "📊 Статистика бота\n\n"
        f"👥 Воронка:\n"
        f"• Прошли опрос: {total}\n"
        f"• Посмотрели гайд: {watched} ({conv_guide}%)\n\n"
        f"📤 Отправлено в Make.com: {total_leads} лидов\n\n"
        f"🔄 Конверсия опрос → гайд: {conv_guide}%\n\n"
        f"📢 База для рассылки: {total} человек"
    )
    await message.answer(text)

# === КОМАНДА /BROADCAST (только для админа) ===
@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    parts = message.text.split(" ", 1)
    if len(parts) < 2:
        await message.answer("⚠️ Напиши: /broadcast твой текст")
        return

    broadcast_text = parts[1]
    sent = 0
    failed = 0

    for uid in completed_users:
        try:
            await bot.send_message(uid, broadcast_text)
            sent += 1
            await asyncio.sleep(0.1)
        except Exception:
            failed += 1

    await message.answer(
        f"✅ Рассылка завершена!\n\n"
        f"📤 Отправлено: {sent}\n"
        f"❌ Не удалось: {failed}\n"
        f"👥 Всего в базе: {len(completed_users)}"
    )

# === АВТООТВЕТЧИК ===
@router.message()
async def auto_reply(message: Message):
    await message.answer(
        "👋 Привет! Я бот для сбора лидов.\n\n"
        "Напиши /start, чтобы пройти опрос и получить бесплатный гайд."
    )

# === ЗАПУСК ===
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
