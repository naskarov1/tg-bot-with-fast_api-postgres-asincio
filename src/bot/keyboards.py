from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiogram.filters.callback_data import CallbackData


# ==========================================
# 1. Callback-фабрики (для Inline-кнопок)
# ==========================================
class ScheduleCB(CallbackData, prefix="sch"):
    action: str  # "edit_title", "edit_time", "delete"
    item_id: int


class HomeworkCB(CallbackData, prefix="hw"):
    action: str  # "edit_text", "delete"
    item_id: int


# ==========================================
# 2. Permanent Reply-клавиатура (внизу экрана)
# ==========================================
def get_main_reply_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()

    # Ряд 1
    builder.row(
        KeyboardButton(text="📅 Расписание"),
        KeyboardButton(text="📝 Добавить ДЗ")
    )
    # Ряд 2 (Новые кнопки управления)
    builder.row(
        KeyboardButton(text="⚙️ Изменить расписание"),
        KeyboardButton(text="✏️ Изменить ДЗ")
    )
    # Ряд 3
    builder.row(
        KeyboardButton(text="📷 Загрузить фото"),
        KeyboardButton(text="🗑 Очистить всё")
    )

    return builder.as_markup(
        resize_keyboard=True,
        persistent=True
    )


# ==========================================
# 3. Inline-клавиатуры (под сообщениями)
# ==========================================
def get_schedule_actions_kb(item_id: int) -> InlineKeyboardMarkup:
    """Inline-кнопки под конкретным занятием"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✏️ Название",
                    callback_data=ScheduleCB(action="edit_title", item_id=item_id).pack(),
                ),
                InlineKeyboardButton(
                    text="🕒 Время",
                    callback_data=ScheduleCB(action="edit_time", item_id=item_id).pack(),
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🗑 Удалить",
                    callback_data=ScheduleCB(action="delete", item_id=item_id).pack(),
                ),
            ],
        ]
    )


def get_homework_actions_kb(item_id: int) -> InlineKeyboardMarkup:
    """Inline-кнопки под конкретным ДЗ"""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✏️ Изменить текст",
                    callback_data=HomeworkCB(action="edit_text", item_id=item_id).pack(),
                ),
                InlineKeyboardButton(
                    text="🗑 Удалить",
                    callback_data=HomeworkCB(action="delete", item_id=item_id).pack(),
                ),
            ]
        ]
    )