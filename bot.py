import asyncio
from aiogram import Bot
from handlers import dp
from config import BOT_TOKEN
from support_handlers import router as support_router
from admin_handlers import setup_admin

bot = Bot(token=BOT_TOKEN)

async def main():
    dp.include_router(support_router)
    setup_admin(dp)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
