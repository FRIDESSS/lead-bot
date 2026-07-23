import asyncio
import logging
import os
import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

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
dp = Dispatcher(storage=storage)

# ========== ОБРАБОТЧИКИ ==========

@dp.message(CommandStart(deep_link=True))
async def cmd_start_deep_link(message: types.Message, state: FSMContext, command: types.BotCommand):
    source = command.args
    await state.update_data(
        source=source,
        user_id=message.from_user.id,
        username=message.from_user.username
    )
    await message.answer("👋 Привет! Давайте познакомимся.\n\nКак вас зовут?")
    await state.set_state(LeadForm.name)

@dp.message(CommandStart())
async def cmd_start_plain(message: types.Message, state: FSMContext):
    await state.update_data(
        source="direct",
        user_id=message.from_user.id,
        username=message.from_user.username
    )
    await message.answer("👋 Привет! Давайте познакомимся.\n\nКак вас зовут?")
    await state.set_state(LeadForm.name)

@dp.message(LeadForm.name)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Какая услуга вас интересует?")
    await state.set_state(LeadForm.service)

@dp.message(LeadForm.service)
async def process_service(message: types.Message, state: FSMContext):
    await state.update_data(service=message.text)
    await message.answer("Какой бюджет вы рассматриваете?")
    await state.set_state(LeadForm.budget)

@dp.message(LeadForm.budget)
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
        "full_dialog": f"Имя: {data['name']}\nУслуга: {data['service']}\nБюджет: {data['budget']}"
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

    await state.clear()

# ========== ЗАПУСК ==========
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
