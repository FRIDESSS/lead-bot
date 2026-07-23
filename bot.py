import asyncio
import logging
import os
import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import CommandStart
from aiogram.dispatcher.filters.state import State, StatesGroup

# Настройки из переменных окружения
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
MAKE_WEBHOOK = os.environ.get("MAKE_WEBHOOK", "")

# ========== FSM ==========
class LeadForm(StatesGroup):
    name = State()
    service = State()
    budget = State()

# ========== ИНИЦИАЛИЗАЦИЯ ==========
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# ========== ОБРАБОТЧИКИ ==========

@dp.message_handler(CommandStart(), state="*")
async def cmd_start(message: types.Message, state: FSMContext):
    args = message.get_args()
    source = args if args else "direct"

    await state.update_data(
        source=source,
        user_id=message.from_user.id,
        username=message.from_user.username
    )
    await message.answer("👋 Привет! Давайте познакомимся.

Как вас зовут?")
    await LeadForm.name.set()

@dp.message_handler(state=LeadForm.name)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Какая услуга вас интересует?")
    await LeadForm.service.set()

@dp.message_handler(state=LeadForm.service)
async def process_service(message: types.Message, state: FSMContext):
    await state.update_data(service=message.text)
    await message.answer("Какой бюджет вы рассматриваете?")
    await LeadForm.budget.set()

@dp.message_handler(state=LeadForm.budget)
async def process_budget(message: types.Message, state: FSMContext):
    await state.update_data(budget=message.text)
    data = await state.get_data()

    payload = {
        "name": data["name"],
        "service": data["service"],
        "budget": data["budget"],
        "source": data["source"],
        "user_id": data["user_id"],
        "username": data.get("username"),
        "full_dialog": f"Имя: {data['name']}
Услуга: {data['service']}
Бюджет: {data['budget']}"
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(MAKE_WEBHOOK, json=payload) as resp:
                if resp.status == 200:
                    await message.answer("✅ Спасибо! Мы скоро с вами свяжемся.")
                else:
                    await message.answer("⚠️ Что-то пошло не так, но мы получили вашу заявку.")
    except Exception as e:
        logging.error(f"Ошибка отправки в Make: {e}")
        await message.answer("⚠️ Ошибка соединения, но заявка сохранена.")

    await state.finish()

# ========== ЗАПУСК ==========
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    executor = __import__('aiogram').utils.executor
    executor.start_polling(dp, skip_updates=True)
