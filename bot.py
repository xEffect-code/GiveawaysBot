import asyncio
from aiogram import Bot, Dispatcher
from config import BOT_TOKEN
from handlers import router as main_router
from support_handlers import router as support_router
from admin_handlers import router as admin_router
from aiogram.fsm.storage.memory import MemoryStorage

bot = Bot(token=BOT_TOKEN)

async def main():
    dp = Dispatcher()
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    dp.include_router(admin_router)
    dp.include_router(main_router)
    dp.include_router(support_router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
