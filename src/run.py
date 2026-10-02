import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

from src.config import settings
from src.database import db_manager
from src.scheduler import NotificationScheduler
from src.bot.handlers import router


async def main():
    # Настраиваем логирование
    logging.basicConfig(level=logging.INFO)

    # 1. Создаем таблицы в БД при старте
    await db_manager.init_db()

    # 2. Инициализируем бота и диспетчер
    bot = Bot(token=settings.BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    # 3. Сбрасываем старый webhook (если случайно ставили)
    await bot.delete_webhook(drop_pending_updates=True)

    # 4. Запускаем сервис уведомлений
    notifier = NotificationScheduler(bot=bot)
    notifier.start()

    logging.info("🚀 Бот запущен в локальном режиме (Long Polling)")

    try:
        await dp.start_polling(bot)
    finally:
        notifier.stop()
        await bot.session.close()
        await db_manager.close()


if __name__ == "__main__":
    asyncio.run(main())