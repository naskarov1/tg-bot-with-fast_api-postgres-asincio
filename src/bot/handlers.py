from datetime import datetime
from aiogram import Router, types, F
from aiogram.filters import Command, or_f, StateFilter
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, update, delete

from src.database import db_manager
from src.models import Schedule, Homework
from src.bot.states import (
    AddScheduleSG,
    AddHomeworkSG,
    EditScheduleSG,
    EditHomeworkSG,
)
from src.bot.keyboards import (
    get_main_reply_keyboard,
    get_schedule_actions_kb,
    get_homework_actions_kb,
    ScheduleCB,
    HomeworkCB,
)

router = Router()

DAYS_OF_WEEK = {
    0: "Понедельник",
    1: "Вторник",
    2: "Среда",
    3: "Четверг",
    4: "Пятница",
    5: "Суббота",
    6: "Воскресенье",
}


# ====================================================
#  1. СТАРТ И ОСНОВНЫЕ КОМАНДЫ
# ====================================================

@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "👋 <b>Добро пожаловать!</b>\n\n"
        "Я ваш бот для расписания и домашних заданий.\n"
        "Используйте кнопки меню внизу для быстрого доступа.",
        reply_markup=get_main_reply_keyboard(),
        parse_mode="HTML",
    )


@router.message(Command("cancel"))
async def cmd_cancel(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "❌ Действие отменено.",
        reply_markup=get_main_reply_keyboard(),
    )


# ====================================================
#  2. ПРОСМОТР РАСПИСАНИЯ И ДЗ
# ====================================================

@router.message(or_f(Command("schedule"), F.text == "📅 Расписание"))
async def cmd_schedule(message: types.Message, state: FSMContext):
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
        await message.answer("📭 У вас пока нет добавленных занятий.")
        return

    text = "📅 <b>Ваше расписание:</b>\n"
    current_day = -1

    for sch in schedules:
        if sch.day_of_week != current_day:
            current_day = sch.day_of_week
            text += f"\n📌 <b>{DAYS_OF_WEEK[current_day]}</b>\n"

        start_str = sch.start_time.strftime("%H:%M")
        end_str = sch.end_time.strftime("%H:%M")
        text += f"└ 🕒 <code>{start_str} - {end_str}</code> — <b>{sch.title}</b>\n"

    await message.answer(text, parse_mode="HTML")


# ====================================================
#  3. УПРАВЛЕНИЕ РАСПИСАНИЕМ (ИЗМЕНЕНИЕ И УДАЛЕНИЕ)
# ====================================================

@router.message(or_f(Command("manage_schedule"), F.text == "⚙️ Изменить расписание"))
async def cmd_manage_schedule(message: types.Message, state: FSMContext):
    await state.clear()

    async for session in db_manager.get_session():
        stmt = (
            select(Schedule)
            .where(Schedule.user_id == message.from_user.id)
            .order_by(Schedule.day_of_week, Schedule.start_time)
        )
        schedules = (await session.execute(stmt)).scalars().all()

    if not schedules:
        await message.answer("📭 Список занятий пуст.")
        return

    await message.answer("⚙️ <b>Выберите занятие для изменения:</b>", parse_mode="HTML")

    for sch in schedules:
        start_str = sch.start_time.strftime("%H:%M")
        end_str = sch.end_time.strftime("%H:%M")
        text = f"📌 <b>{sch.title}</b>\n└ День: {DAYS_OF_WEEK[sch.day_of_week]} | Time: <code>{start_str}-{end_str}</code>"

        # Подключаем Inline-клавиатуру к каждому сообщению
        await message.answer(
            text,
            reply_markup=get_schedule_actions_kb(sch.id),
            parse_mode="HTML",
        )


@router.callback_query(ScheduleCB.filter(F.action == "delete"))
async def process_delete_schedule(callback: types.CallbackQuery, callback_data: ScheduleCB):
    async for session in db_manager.get_session():
        stmt = delete(Schedule).where(
            Schedule.id == callback_data.item_id,
            Schedule.user_id == callback.from_user.id,
        )
        await session.execute(stmt)
        await session.commit()

    await callback.message.edit_text("✅ Занятие удалено.")
    await callback.answer()


@router.callback_query(ScheduleCB.filter(F.action == "edit_title"))
async def start_edit_schedule_title(callback: types.CallbackQuery, callback_data: ScheduleCB, state: FSMContext):
    await state.update_data(editing_item_id=callback_data.item_id)
    await state.set_state(EditScheduleSG.waiting_for_new_title)
    await callback.message.answer("Введите новое название для этого занятия:")
    await callback.answer()


@router.message(EditScheduleSG.waiting_for_new_title, F.text)
async def process_new_schedule_title(message: types.Message, state: FSMContext):
    if message.text.startswith("/") or message.text.startswith("📅") or message.text.startswith(
            "📝") or message.text.startswith("⚙️") or message.text.startswith("✏️"):
        await state.clear()
        return

    data = await state.get_data()
    item_id = data.get("editing_item_id")

    async for session in db_manager.get_session():
        stmt = update(Schedule).where(Schedule.id == item_id).values(title=message.text)
        await session.execute(stmt)
        await session.commit()

    await state.clear()
    await message.answer(f"✅ Название изменено на: <b>{message.text}</b>", parse_mode="HTML")


@router.callback_query(ScheduleCB.filter(F.action == "edit_time"))
async def start_edit_schedule_time(callback: types.CallbackQuery, callback_data: ScheduleCB, state: FSMContext):
    await state.update_data(editing_item_id=callback_data.item_id)
    await state.set_state(EditScheduleSG.waiting_for_new_time)
    await callback.message.answer("Введите новое время в формате <b>HH:MM-HH:MM</b> (например, 09:00-10:30):",
                                  parse_mode="HTML")
    await callback.answer()


@router.message(EditScheduleSG.waiting_for_new_time, F.text)
async def process_new_schedule_time(message: types.Message, state: FSMContext):
    if message.text.startswith("/") or message.text.startswith("📅") or message.text.startswith(
            "📝") or message.text.startswith("⚙️") or message.text.startswith("✏️"):
        await state.clear()
        return

    try:
        start_str, end_str = message.text.split("-")
        start_time = datetime.strptime(start_str.strip(), "%H:%M").time()
        end_time = datetime.strptime(end_str.strip(), "%H:%M").time()
    except ValueError:
        await message.answer("⚠️ Неверный формат! Введите время как 09:00-10:30:")
        return

    data = await state.get_data()
    item_id = data.get("editing_item_id")

    async for session in db_manager.get_session():
        stmt = update(Schedule).where(Schedule.id == item_id).values(start_time=start_time, end_time=end_time)
        await session.execute(stmt)
        await session.commit()

    await state.clear()
    await message.answer("✅ Время занятия успешно обновлено!")


# ====================================================
#  4. УПРАВЛЕНИЕ ДОМАШНИМ ЗАДАНИЕМ (ИЗМЕНЕНИЕ И УДАЛЕНИЕ)
# ====================================================

@router.message(or_f(Command("manage_hw"), F.text == "✏️ Изменить ДЗ"))
async def cmd_manage_hw(message: types.Message, state: FSMContext):
    await state.clear()

    async for session in db_manager.get_session():
        stmt = select(Homework).where(Homework.user_id == message.from_user.id)
        homeworks = (await session.execute(stmt)).scalars().all()

    if not homeworks:
        await message.answer("📭 Активных домашних заданий нет.")
        return

    await message.answer("✏️ <b>Выберите домашнее задание для изменения:</b>", parse_mode="HTML")

    for hw in homeworks:
        text = f"📖 <b>{hw.title}</b>\n└ {hw.description}"
        await message.answer(
            text,
            reply_markup=get_homework_actions_kb(hw.id),
            parse_mode="HTML",
        )


@router.callback_query(HomeworkCB.filter(F.action == "delete"))
async def process_delete_hw(callback: types.CallbackQuery, callback_data: HomeworkCB):
    async for session in db_manager.get_session():
        stmt = delete(Homework).where(
            Homework.id == callback_data.item_id,
            Homework.user_id == callback.from_user.id,
        )
        await session.execute(stmt)
        await session.commit()

    await callback.message.edit_text("✅ Домашнее задание удалено!")
    await callback.answer()


@router.callback_query(HomeworkCB.filter(F.action == "edit_text"))
async def start_edit_hw_text(callback: types.CallbackQuery, callback_data: HomeworkCB, state: FSMContext):
    await state.update_data(editing_hw_id=callback_data.item_id)
    await state.set_state(EditHomeworkSG.waiting_for_new_text)
    await callback.message.answer("Введите новое описание для домашнего задания:")
    await callback.answer()


@router.message(EditHomeworkSG.waiting_for_new_text, F.text)
async def process_new_hw_text(message: types.Message, state: FSMContext):
    if message.text.startswith("/") or message.text.startswith("📅") or message.text.startswith(
            "📝") or message.text.startswith("⚙️") or message.text.startswith("✏️"):
        await state.clear()
        return

    data = await state.get_data()
    hw_id = data.get("editing_hw_id")

    async for session in db_manager.get_session():
        stmt = update(Homework).where(Homework.id == hw_id).values(description=message.text)
        await session.execute(stmt)
        await session.commit()

    await state.clear()
    await message.answer("✅ Текст домашнего задания успешно обновлен!")