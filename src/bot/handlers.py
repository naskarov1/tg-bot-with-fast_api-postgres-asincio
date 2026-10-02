from datetime import datetime, time, date
import re
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from sqlalchemy import select

from src.database import db_manager
from src.models import User, Schedule, Homework
from src.bot.states import AddScheduleSG, AddHomeworkSG
from src.bot.keyboards import (
    DAYS_OF_WEEK,
    get_days_keyboard,
    get_remind_offset_keyboard,
    get_schedules_keyboard,
    get_main_reply_keyboard,
)

router = Router()


# --- Базовые команды ---

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    """Регистрация пользователя и приветствие."""
    async for session in db_manager.get_session():
        user = await session.get(User, message.from_user.id)
        if not user:
            user = User(id=message.from_user.id)
            session.add(user)
            await session.commit()
    await message.answer(
        "👋 **Привет! Я бот для управления расписанием и ДЗ.**\n\n"
        "Доступные команды:\n"
        "➕ /add_task - Добавить занятие в расписание\n"
        "📝 /add_hw - Добавить домашнее задание к занятию\n"
        "📅 /schedule - Посмотреть расписание\n"
        "⚙️ /settings - Настройки уведомлений\n"
        "❌ /cancel - Отменить дейтсавие",
        parse_mode="HTML", reply_markup=get_main_reply_keyboard()
    )


# --- FSM 1: Добавление занятия в расписание ---
@router.message(Command("add_task"))
@router.message(F.text == "➕ Добавить занятие в расписание")
async def cmd_add_task(message: types.Message, state: FSMContext):
    await state.set_state(AddScheduleSG.title)
    await message.answer("Введите название предмета или задачи (например: *Математика*):", parse_mode="HTML")


@router.message(AddScheduleSG.title)
async def process_title(message: types.Message, state: FSMContext):
    await state.clear()
    await state.update_data(title=message.text.strip())
    await state.set_state(AddScheduleSG.day_of_week)
    await message.answer("Выберите день недели:", reply_markup=get_days_keyboard())


@router.callback_query(AddScheduleSG.day_of_week, F.data.startswith("select_day:"))
async def process_day_of_week(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    day_idx = int(callback.data.split(":")[1])
    await state.update_data(day_of_week=day_idx)
    await state.set_state(AddScheduleSG.time_range)

    await callback.message.edit_text(
        f"Выбран день: *{DAYS_OF_WEEK[day_idx]}*\n\n"
        "Введите время начала и конца в формате `ЧЧ:ММ ЧЧ:ММ` (например: `10:00 11:30`):",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(AddScheduleSG.time_range)
async def process_time_range(message: types.Message, state: FSMContext):
    await state.clear()
    pattern = r"^([0-1]?\d|2[0-3]):([0-5]\d)\s+([0-1]?\d|2[0-3]):([0-5]\d)$"
    match = re.match(pattern, message.text.strip())

    if not match:
        await message.answer("❌ Неверный формат! Напишите время так: `10:00 11:30`", parse_mode="HTML")
        return

    start_h, start_m, end_h, end_m = map(int, match.groups())
    start_time_val = time(start_h, start_m)
    end_time_val = time(end_h, end_m)

    if start_time_val >= end_time_val:
        await message.answer("❌ Время окончания должно быть позже начала!")
        return

    await state.update_data(
        start_time_str=start_time_val.strftime("%H:%M"),
        end_time_str=end_time_val.strftime("%H:%M")
    )
    await state.set_state(AddScheduleSG.remind_offset)
    await message.answer("За сколько минут до занятия напоминать?", reply_markup=get_remind_offset_keyboard())


@router.callback_query(AddScheduleSG.remind_offset, F.data.startswith("remind_offset:"))
async def process_remind_offset(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    offset_val = callback.data.split(":")[1]
    remind_offset = None if offset_val == "default" else int(offset_val)

    data = await state.get_data()
    user_id = callback.from_user.id

    start_t = datetime.strptime(data["start_time_str"], "%H:%M").time()
    end_t = datetime.strptime(data["end_time_str"], "%H:%M").time()

    async for session in db_manager.get_session():
        schedule = Schedule(
            user_id=user_id,
            title=data["title"],
            day_of_week=data["day_of_week"],
            start_time=start_t,
            end_time=end_t,
            remind_offset=remind_offset
        )
        session.add(schedule)
        await session.commit()

    remind_text = "По умолчанию" if remind_offset is None else f"За {remind_offset} мин"

    await callback.message.edit_text(
        f"✅ **Занятие добавлено!**\n\n"
        f"📌 **Предмет:** {data['title']}\n"
        f"📅 **День:** {DAYS_OF_WEEK[data['day_of_week']]}\n"
        f"⏰ **Время:** {data['start_time_str']} - {data['end_time_str']}\n"
        f"🔔 **Уведомление:** {remind_text}",
        parse_mode="HTML"
    )
    await state.clear()
    await callback.answer()


# --- FSM 2: Добавление домашнего задания ---
@router.message(Command("add_hw"))
@router.message(F.text == "📝 Добавить домашнее задание к занятию")
async def cmd_add_hw(message: types.Message, state: FSMContext):
    await state.clear()

    async for session in db_manager.get_session():
        stmt = (
            select(Schedule)
            .where(Schedule.user_id == message.from_user.id)
            .order_by(Schedule.day_of_week, Schedule.start_time)
        )
        result = await session.execute(stmt)
        schedules = result.scalars().all()

    if not schedules:
        await message.answer("❌ У вас еще нет занятий. Сначала добавьте предмет через /add_task")
        return

    await state.set_state(AddHomeworkSG.select_schedule)
    await message.answer("Выберите предмет для добавления ДЗ:", reply_markup=get_schedules_keyboard(schedules))


@router.callback_query(AddHomeworkSG.select_schedule, F.data.startswith("select_schedule:"))
async def process_select_schedule_for_hw(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()

    schedule_id = int(callback.data.split(":")[1])
    await state.update_data(schedule_id=schedule_id)
    await state.set_state(AddHomeworkSG.text)
    await callback.message.edit_text("Введите описание домашнего задания:")
    await callback.answer()


@router.message(AddHomeworkSG.text)
async def process_hw_text(message: types.Message, state: FSMContext):
    await state.clear()

    await state.update_data(text=message.text.strip())
    await state.set_state(AddHomeworkSG.due_date)
    today_str = date.today().strftime("%Y-%m-%d")
    await message.answer(f"Введите дату сдачи в формате `ГГГГ-ММ-ДД` (например: `{today_str}`):", parse_mode="HTML")


@router.message(AddHomeworkSG.due_date)
async def process_hw_due_date(message: types.Message, state: FSMContext):
    await state.clear()
    try:
        due_date_val = datetime.strptime(message.text.strip(), "%Y-%m-%d").date()
    except ValueError:
        await message.answer("❌ Неверный формат! Используйте формат `ГГГГ-ММ-ДД`", parse_mode="HTML")
        return

    data = await state.get_data()

    async for session in db_manager.get_session():
        hw = Homework(
            schedule_id=data["schedule_id"],
            text=data["text"],
            due_date=due_date_val
        )
        session.add(hw)
        await session.commit()

    await message.answer(
        f"✅ **ДЗ успешно добавлено!**\n\n"
        f"📝 **Текст:** {data['text']}\n"
        f"📅 **Сдать до:** {due_date_val.strftime('%d.%m.%Y')}",
        parse_mode="HTML"
    )
    await state.clear()
@router.message(Command("cancel"))
@router.message(F.text == "❌ Отменить дейтсавие")
async def cmd_cancel(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Действие отменено.")