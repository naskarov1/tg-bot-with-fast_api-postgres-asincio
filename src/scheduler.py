from datetime import datetime, timedelta
from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select

from src.database import db_manager
from src.models import Schedule, User


class NotificationScheduler:
    def __init__(self, bot: Bot):
        self.bot = bot
        self.scheduler = AsyncIOScheduler()

    async def check_and_send_notifications(self) -> None:
        now = datetime.now()
        current_day = now.weekday()

        async for session in db_manager.get_session():
            stmt = (
                select(Schedule, User)
                .join(User, Schedule.user_id == User.id)
                .where(
                    Schedule.day_of_week == current_day,
                    User.notifications_enabled.is_(True),
                )
            )
            result = await session.execute(stmt)
            for schedule, user in result.all():
                offset = (
                    schedule.remind_offset
                    if schedule.remind_offset is not None
                    else user.default_remind_offset
                )
                task_dt = datetime.combine(now.date(), schedule.start_time)
                notify_dt = task_dt - timedelta(minutes=offset)

                if notify_dt.hour == now.hour and notify_dt.minute == now.minute:
                    text = (
                        f"⏰ **Напоминание о занятии!**\n\n"
                        f"📌 **{schedule.title}**\n"
                        f"🕒 Начало в {schedule.start_time.strftime('%H:%M')} (через {offset} мин)"
                    )
                    try:
                        await self.bot.send_message(
                            chat_id=user.id,
                            text=text,
                            parse_mode="Markdown",
                        )
                    except Exception as e:
                        print(f"Ошибка отправки сообщения: {e}")

    def start(self) -> None:
        self.scheduler.add_job(
            self.check_and_send_notifications,
            trigger="cron",
            second=0,
        )
        self.scheduler.start()

    def stop(self) -> None:
        self.scheduler.shutdown()