import asyncio
import json
import logging
import os
from datetime import datetime

import aiohttp
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode, ContentType
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

# === НАСТРОЙКИ ===
BOT_TOKEN = os.getenv("BOT_TOKEN", "8814234982:AAHLYcKXiG2WC8xVG_PT3tvPf70SELhkpHs")
MAKE_WEBHOOK = os.getenv("MAKE_WEBHOOK", "https://hook.eu1.make.com/q3kmdwgx11em4uyr89wamx3t1rcj8fim")

MANAGER_USERNAME = "Psycho_tipe"
MANAGER_LINK = "https://t.me/" + MANAGER_USERNAME
FREE_GUIDE_LINK = "https://vkvideo.ru/video-35647551_456284706"
MAIN_PRODUCT_LINK = MANAGER_LINK

ADMIN_ID = 5842806238

# === ФАЙЛ ДЛЯ БЭКАПА ===
BACKUP_FILE = "users_backup.json"

# === ЛОГИ ===
logging.basicConfig(level=logging.INFO)

# === БОТ + ДИСПЕТЧЕР ===
bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
router = Router()
dp.include_router(router)

# === СОСТОЯНИЯ ===
class LeadForm(StatesGroup):
    name = State()
    age = State()
    goal = State()
    source = State()

# === ХРАНИЛИЩЕ ===
completed_users = set()
watched_guide = set()
total_leads = 0

# === БЭКАП: ЗАГРУЗКА ===
def load_backup():
    global completed_users, watched_guide, total_leads
    if os.path.exists(BACKUP_FILE):
        try:
            with open(BACKUP_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                completed_users = set(data.get("completed_users", []))
                watched_guide = set(data.get("watched_guide", []))
                total_leads = data.get("total_leads", 0)
            logging.info("Бэкап загружен: " + str(len(completed_users)) + " пользователей")
        except Exception as e:
            logging.error("Ошибка загрузки бэкапа: " + str(e))

# === БЭКАП: СОХРАНЕНИЕ ===
def save_backup():
    try:
        data = {
            "completed_users": list(completed_users),
            "watched_guide": list(watched_guide),
            "total_leads": total_leads
        }
        with open(BACKUP_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error("Ошибка сохранения бэкапа: " + str(e))

# === КЛАВИАТУРЫ ===
def get_watched_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ Посмотрел", callback_data="watched")]
        ]
    )

def get_product_kb():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔥 Узнать о курсе", url=MAIN_PRODUCT_LINK)],
            [InlineKeyboardButton(text="💬 Написать менеджеру", url=MANAGER_LINK)]
        ]
    )

# === ПРОВЕРКА АДМИНА ===
def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

# === ВАЛИДАЦИЯ ===
async def validate_text(message: Message, state: FSMContext, retry_prompt: str):
    if message.content_type != ContentType.TEXT:
        await message.answer(
            "⚠️ Пожалуйста, напиши ответ <b>текстом</b>.\n\n" + retry_prompt
        )
        return False
    if not message.text.strip():
        await message.answer(
            "⚠️ Ответ не может быть пустым.\n\n" + retry_prompt
        )
        return False
    return True

# === ОТПРАВКА В MAKE.COM ===
async def send_to_make(data: dict):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(MAKE_WEBHOOK, json=data, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                logging.info("Make.com ответ: " + str(resp.status))
                return resp.status == 200
    except Exception as e:
        logging.error("Make.com ошибка: " + str(e))
        return False

# === КОМАНДА /START ===
@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, command: CommandStart):
    user_id = message.from_user.id

    if user_id in completed_users:
        await message.answer(
            "👋 Привет снова!\n\n"
            "Ты уже проходил(а) опрос. Вот твой гайд:\n"
            "<a href=\"" + FREE_GUIDE_LINK + "\">👉 Открыть гайд</a>",
            reply_markup=get_watched_kb(),
            disable_web_page_preview=True
        )
        return

    await state.clear()
    utm = command.args if command.args else "direct"
    await state.update_data(utm=utm)

    text = (
        "👋 Привет! Рад тебя видеть.\n\n"
        "🎁 У меня для тебя есть кое-что полезное — <b>бесплатный гайд</b>, "
        "который поможет сделать первый шаг.\n\n"
        "Чтобы получить доступ, пройди небольшой мини-опрос (всего 4 вопроса). "
        "Это займет буквально минуту.\n\n"
        "Готов(а)? Тогда поехали! 🚀"
    )
    await message.answer(text)
    await state.set_state(LeadForm.name)
    await message.answer("Как тебя зовут? (можно имя или псевдоним)")

# === КОМАНДА /RESET (только админ) ===
@router.message(Command("reset"))
async def cmd_reset(message: Message):
    if not is_admin(message.from_user.id):
        return

    user_id = message.from_user.id
    removed = False

    if user_id in completed_users:
        completed_users.discard(user_id)
        removed = True
    if user_id in watched_guide:
        watched_guide.discard(user_id)

    save_backup()

    if removed:
        await message.answer("✅ Твои данные сброшены! Теперь можешь пройти опрос заново.")
    else:
        await message.answer("ℹ️ Ты и так не проходил(а) опрос. Можешь начать с /start")

# === КОМАНДА /STATS (только админ) ===
@router.message(Command("stats"))
async def cmd_stats(message: Message):
    if not is_admin(message.from_user.id):
        return

    conversion_to_guide = 0
    if completed_users:
        conversion_to_guide = round(len(watched_guide) / len(completed_users) * 100, 1)

    text = (
        "📊 <b>Статистика бота</b>\n\n"
        "👥 <b>Воронка:</b>\n"
        "• Прошли опрос: " + str(len(completed_users)) + "\n"
        "• Посмотрели гайд: " + str(len(watched_guide)) + " (" + str(conversion_to_guide) + "%)\n\n"
        "📤 <b>Отправлено в Make.com:</b> " + str(total_leads) + " лидов\n\n"
        "🔄 Конверсия опрос → гайд: <b>" + str(conversion_to_guide) + "%</b>\n\n"
        "📢 <b>База для рассылки:</b> " + str(len(completed_users)) + " человек"
    )
    await message.answer(text)

# === КОМАНДА /BROADCAST (только админ) ===
@router.message(Command("broadcast"))
async def cmd_broadcast(message: Message):
    if not is_admin(message.from_user.id):
        return

    parts = message.text.split(" ", 1)
    if len(parts) < 2 or not parts[1].strip():
        await message.answer(
            "⚠️ Напиши сообщение после команды.\n\n"
            "Пример:\n"
            "/broadcast 🔥 Вышел новый модуль! Успей забрать со скидкой"
        )
        return

    broadcast_text = parts[1].strip()

    if not completed_users:
        await message.answer("⚠️ База пустая. Никто ещё не прошёл опрос.")
        return

    sent = 0
    failed = 0

    for user_id in completed_users:
        try:
            await bot.send_message(user_id, broadcast_text)
            sent += 1
            await asyncio.sleep(0.1)
        except Exception as e:
            logging.error("Ошибка рассылки user " + str(user_id) + ": " + str(e))
            failed += 1

    await message.answer(
        "✅ <b>Рассылка завершена!</b>\n\n"
        "📤 Отправлено: " + str(sent) + "\n"
        "❌ Не удалось: " + str(failed) + "\n"
        "👥 Всего в базе: " + str(len(completed_users))
    )

# === ОПРОС ===
@router.message(LeadForm.name)
async def process_name(message: Message, state: FSMContext):
    if not await validate_text(message, state, "Как тебя зовут? (можно имя или псевдоним)"):
        return
    await state.update_data(name=message.text.strip())
    await state.set_state(LeadForm.age)
    await message.answer("Сколько тебе лет?")

@router.message(LeadForm.age)
async def process_age(message: Message, state: FSMContext):
    if not await validate_text(message, state, "Сколько тебе лет?"):
        return
    age_text = message.text.strip()
    if not age_text.isdigit():
        await message.answer(
            "⚠️ Пожалуйста, укажи возраст <b>числом</b>.\n\n"
            "Например: 25"
        )
        return
    await state.update_data(age=age_text)
    await state.set_state(LeadForm.goal)
    await message.answer("Какая у тебя цель? (напиши своими словами)")

@router.message(LeadForm.goal)
async def process_goal(message: Message, state: FSMContext):
    if not await validate_text(message, state, "Какая у тебя цель? (напиши своими словами)"):
        return
    await state.update_data(goal=message.text.strip())
    await state.set_state(LeadForm.source)
    await message.answer("Откуда ты узнал(а) обо мне? (Instagram, VK, друзья, реклама и т.д.)")

@router.message(LeadForm.source)
async def process_source(message: Message, state: FSMContext):
    if not await validate_text(message, state, "Откуда ты узнал(а) обо мне? (Instagram, VK, друзья, реклама и т.д.)"):
        return

    data = await state.get_data()
    name = data.get("name", "Не указано")
    age = data.get("age", "Не указано")
    goal = data.get("goal", "Не указано")
    source = message.text.strip()
    utm = data.get("utm", "direct")

    user = message.from_user
    user_id = str(user.id)
    username = user.username or "None"
    full_dialog = "Имя: " + name + " | Возраст: " + age + " | Цель: " + goal + " | Откуда: " + source

    completed_users.add(message.from_user.id)
    save_backup()

    payload = {
        "name": name,
        "age": age,
        "goal": goal,
        "source": source,
        "utm": utm,
        "user_id": user_id,
        "username": username,
        "full_dialog": full_dialog,
        "timestamp": datetime.now().strftime("%d.%m.%Y %H:%M")
    }

    success = await send_to_make(payload)
    global total_leads

    if success:
        total_leads += 1
        save_backup()
        logging.info("Лид отправлен: " + name)
    else:
        logging.warning("Лид НЕ отправлен в Make.com: " + name)
        await message.answer(
            "⚠️ <b>Технические неполадки</b> при сохранении данных, "
            "но твой гайд я всё равно выдаю!"
        )

    text = (
        "✅ Спасибо за ответы!\n\n"
        "📎 Вот твой <b>бесплатный гайд</b> — вводная часть курса:\n"
        "<a href=\"" + FREE_GUIDE_LINK + "\">👉 Открыть гайд</a>\n\n"
        "Посмотри материал и нажми кнопку ниже 👇"
    )
    await message.answer(text, reply_markup=get_watched_kb(), disable_web_page_preview=True)
    await state.clear()

# === CALLBACK: ПОСМОТРЕЛ ===
@router.callback_query(F.data == "watched")
async def on_watched(callback: CallbackQuery):
    await callback.answer("Отлично! 🎉")
    watched_guide.add(callback.from_user.id)
    save_backup()

    text = (
        "🎉 Поздравляю! Ты просмотрел(а) вводную часть курса.\n\n"
        "Теперь ты понимаешь, в каком направлении двигаться.\n\n"
        "🔥 <b>Хочешь углубиться и получить полную программу?</b>\n\n"
        "Основной курс включает:\n"
        "• Пошаговую методику\n"
        "• Практические задания\n"
        "• Поддержку и обратную связь\n"
        "• Доступ к закрытому сообществу\n\n"
        "Нажми кнопку ниже, чтобы узнать подробности 👇"
    )
    await callback.message.answer(text, reply_markup=get_product_kb())

# === АВТООТВЕТЧИК ===
@router.message()
async def unknown_message(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None and not is_admin(message.from_user.id):
        await message.answer(
            "👋 Привет! Я не понимаю это сообщение.\n\n"
            "Напиши /start, чтобы получить бесплатный гайд и пройти мини-опрос."
        )

# === ЗАПУСК ===
async def main():
    load_backup()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
