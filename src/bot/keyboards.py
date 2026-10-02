from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardMarkup, KeyboardButton

DAYS_OF_WEEK = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота", "Воскресенье"]


def get_days_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for index, day in enumerate(DAYS_OF_WEEK):
        builder.button(text=day, callback_data=f"select_day:{index}")
    builder.adjust(2)
    return builder.as_markup()


def get_remind_offset_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Отключить уведомление", callback_data="remind_offset:default")
    for offset in [10, 20, 30, 60]:
        builder.button(text=f"За {offset} мин", callback_data=f"remind_offset:{offset}")
    builder.adjust(2)
    return builder.as_markup()


def get_schedules_keyboard(schedules) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for sch in schedules:
        day_str = DAYS_OF_WEEK[sch.day_of_week][:2]
        time_str = sch.start_time.strftime("%H:%M")
        builder.button(
            text=f"{sch.title} ({day_str} {time_str})",
            callback_data=f"select_schedule:{sch.id}",
        )
    builder.adjust(1)
    return builder.as_markup()
def get_main_reply_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="➕ Добавить занятие в расписание"),
                KeyboardButton(text="📝 Добавить домашнее задание к занятию"),
            ],
            [
                KeyboardButton(text="📅 Посмотреть расписание" ),
                KeyboardButton(text="⚙️ Настройки уведомлений"),
            ],
            [
                KeyboardButton(text="❌ Отменить дейтсавие"),
            ]
        ],
        resize_keyboard=True,  # Делает кнопки аккуратными и компактными
        persistent=True,  # Клавиатура остаётся зафиксированной внизу
    )