#
# from contextlib import asynccontextmanager
# from fastapi import FastAPI, Request
# from aiogram import Bot, Dispatcher, types
# from aiogram.fsm.storage.memory import MemoryStorage
#
# from src.config import settings
# from src.database import db_manager
# from src.scheduler import NotificationScheduler
# from src.bot.handlers import router
#
# bot = Bot(token=settings.BOT_TOKEN)
# dp = Dispatcher(storage=MemoryStorage())
# dp.include_router(router)
#
# notifier = NotificationScheduler(bot=bot)
#
#
# @asynccontextmanager
# async def lifespan(app: FastAPI):
#     # 1. Инициализация таблиц БД
#     await db_manager.init_db()
#
#     # 2. Установка Webhook для Telegram
#     await bot.set_webhook(
#         url=settings.webhook_url,
#         drop_pending_updates=True
#     )
#
#     # 3. Запуск планировщика уведомлений
#     notifier.start()
#
#     yield
#
#     # Остановка сервисов при выключении FastAPI
#     notifier.stop()
#     await bot.delete_webhook()
#     await bot.session.close()
#     await db_manager.close()
#
#
# app = FastAPI(title="Telegram Schedule Bot", lifespan=lifespan)
#
#
# @app.post(settings.WEBHOOK_PATH)
# async def bot_webhook(request: Request):
#     """Прием обновлений от сервера Telegram."""
#     update_data = await request.json()
#     update = types.Update.model_validate(update_data, context={"bot": bot})
#     await dp.feed_update(bot, update)
#     return {"status": "ok"}