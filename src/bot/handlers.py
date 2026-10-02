import io
import re
from datetime import datetime

import easyocr
from aiogram import Router, types, F
from aiogram.filters import Command, or_f
from aiogram.fsm.context import FSMContext
from sqlalchemy import select, update, delete

from src.database import db_manager
from src.models import Schedule, Homework
from src.bot.states import (
    AddScheduleSG,
    AddHomeworkSG,
    EditScheduleSG,
    EditHomeworkSG,
    UploadSchedulePhotoSG,
)
from src.bot.keyboards import (
    get_main_reply_keyboard,
    get_schedule_actions_kb,
    get_homework_actions_kb,
    ScheduleCB,
    HomeworkCB,
)

router = Router()

# Инициализация EasyOCR (работает локально на CPU)
reader = easyocr.Reader(['ru', 'en'], gpu=False)

DAYS_OF_WEEK = {
    0: "Понедельник",
    1: "Вторник",
    2: "Среда",
    3: "Четверг",
    4: "Пятница",
    5: "Суббота",
    6: "Воскресенье",
}

# Фиксированные временные интервалы для 7 уроков
DEFAULT_TIME_SLOTS = [
    (datetime.strptime("08:00", "%H:%M").time(), datetime.strptime("08:40", "%H:%M").time()),
    (datetime.strptime("08:50", "%H:%M").time(), datetime.strptime("09:30", "%H:%M").time()),
    (datetime.strptime("09:40", "%H:%M").time(), datetime.strptime("10:20", "%H:%M").time()),
    (datetime.strptime("10:40", "%H:%M").time(), datetime.strptime("11:20", "%H:%M").time()),
    (datetime.strptime("11:35", "%H:%M").time(), datetime.strptime("12:15", "%H:%M").time()),
    (datetime.strptime("12:25", "%H:%M").time(), datetime.strptime("13:05", "%H:%M").time()),
    (datetime.strptime("13:10", "%H:%M").time(), datetime.strptime("13:50", "%H:%M").time()),
]


def parse_schedule_text(recognized_blocks: list) -> list[dict]:
    """
    Парсер с динамическим определением колонок по заголовкам дней недели
    и привязкой предметов по ближайшей горизонтальной координате (X).
    """
    parsed_items = []

    # Карта названий дней недели к их индексам (0=Пн ... 5=Сб)
    day_keywords = {
        "понедельник": 0, "пн": 0,
        "вторник": 1, "вт": 1,
        "среда": 2, "ср": 2,
        "четверг": 3, "чт": 3,
        "пятница": 4, "пт": 4,
        "суббота": 5, "сб": 5,
    }

    # 1. Находим X-координаты заголовков дней недели
    day_centers = {}  # {day_index: center_x}
    clean_blocks = []

    for bbox, text, prob in recognized_blocks:
        t = text.strip()
        if not t:
            continue

        cx = sum(p[0] for p in bbox) / 4.0
        cy = sum(p[1] for p in bbox) / 4.0
        t_lower = t.lower()

        # Проверяем, является ли блок заголовком дня недели
        found_day = None
        for key, day_idx in day_keywords.items():
            if key in t_lower:
                found_day = day_idx
                break

        if found_day is not None:
            day_centers[found_day] = cx
            continue

        # Отсеиваем служебный текст, номер уроков и время
        if any(h in t_lower for h in ["№", "время", "урок"]) or t in ["—", "-", ""]:
            continue
        if re.search(r"\d{1,2}[\:\.\;]\d{2}", t):
            continue

        clean_blocks.append({"cx": cx, "cy": cy, "text": t})

    # Если заголовки дней недели не распознались, прекращаем
    if not day_centers:
        return []

    # Отфильтровываем цифры 1-7 в первой колонке (номера уроков)
    min_day_x = min(day_centers.values())
    filtered_blocks = []
    for b in clean_blocks:
        if b["text"] in ["1", "2", "3", "4", "5", "6", "7"] and b["cx"] < min_day_x:
            continue
        filtered_blocks.append(b)

    if not filtered_blocks:
        return []

    sorted_days = sorted(day_centers.items(), key=lambda item: item[1])

    # 2. Определяем строки (уроков 1-7) по Y-координатам
    min_y = min(b["cy"] for b in filtered_blocks)
    max_y = max(b["cy"] for b in filtered_blocks)
    row_height = (max_y - min_y) / 6.0 if max_y > min_y else 1.0

    # 3. Распределяем предметы по ближайшему дню и строке
    for b in filtered_blocks:
        # Находим ближайший день по X
        closest_day = min(sorted_days, key=lambda item: abs(item[1] - b["cx"]))[0]

        # Находим номер урока (0..6) по Y
        row_idx = int(round((b["cy"] - min_y) / row_height)) if row_height > 0 else 0
        row_idx = max(0, min(6, row_idx))

        start_time, end_time = DEFAULT_TIME_SLOTS[row_idx]
        clean_title = b["text"].split("\n")[0].strip(" ,.-")

        if len(clean_title) > 1 and not clean_title.isdigit():
            parsed_items.append({
                "day_of_week": closest_day,
                "start_time": start_time,
                "end_time": end_time,
                "title": clean_title,
            })

    return parsed_items


# ====================================================
#  1. ОСНОВНЫЕ КОМАНДЫ И НАВИГАЦИЯ
# ====================================================

@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "👋 <b>Добро пожаловать!</b>\n\n"
        "Я ваш бот для управления расписанием и домашними заданиями.\n"
        "Используйте кнопки меню внизу для быстрой навигации.",
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
#  2. ПРОСМОТР РАСПИСАНИЯ
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

    await message.answer("⚙️ <b>Выберите занятие для управления:</b>", parse_mode="HTML")

    for sch in schedules:
        start_str = sch.start_time.strftime("%H:%M")
        end_str = sch.end_time.strftime("%H:%M")
        text = f"📌 <b>{sch.title}</b>\n└ День: {DAYS_OF_WEEK[sch.day_of_week]} | Время: <code>{start_str}-{end_str}</code>"

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

    await callback.message.edit_text("✅ Занятие успешно удалено.")
    await callback.answer()


@router.callback_query(ScheduleCB.filter(F.action == "edit_title"))
async def start_edit_schedule_title(callback: types.CallbackQuery, callback_data: ScheduleCB, state: FSMContext):
    await state.update_data(editing_item_id=callback_data.item_id)
    await state.set_state(EditScheduleSG.waiting_for_new_title)
    await callback.message.answer("Введите новое название для этого занятия:")
    await callback.answer()


@router.message(EditScheduleSG.waiting_for_new_title, F.text)
async def process_new_schedule_title(message: types.Message, state: FSMContext):
    if message.text.startswith("/") or message.text in [
        "📅 Расписание", "📝 Добавить ДЗ", "⚙️ Изменить расписание",
        "✏️ Изменить ДЗ", "📷 Загрузить фото", "🗑 Очистить всё"
    ]:
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
    await callback.message.answer("Введите новое время в формате <b>HH:MM-HH:MM</b> (например, 09:00-10:30):", parse_mode="HTML")
    await callback.answer()


@router.message(EditScheduleSG.waiting_for_new_time, F.text)
async def process_new_schedule_time(message: types.Message, state: FSMContext):
    if message.text.startswith("/") or message.text in [
        "📅 Расписание", "📝 Добавить ДЗ", "⚙️ Изменить расписание",
        "✏️ Изменить ДЗ", "📷 Загрузить фото", "🗑 Очистить всё"
    ]:
        await state.clear()
        return

    try:
        start_str, end_str = message.text.split("-")
        start_time = datetime.strptime(start_str.strip(), "%H:%M").time()
        end_time = datetime.strptime(end_str.strip(), "%H:%M").time()
    except ValueError:
        await message.answer("⚠️ Неверный формат! Введите время корректно, например: <code>09:00-10:30</code>", parse_mode="HTML")
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
#  4. УПРАВЛЕНИЕ ДОМАШНИМ ЗАДАНИЕМ
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
    if message.text.startswith("/") or message.text in [
        "📅 Расписание", "📝 Добавить ДЗ", "⚙️ Изменить расписание",
        "✏️ Изменить ДЗ", "📷 Загрузить фото", "🗑 Очистить всё"
    ]:
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


# ====================================================
#  5. РАСПОЗНАВАНИЕ ТАБЛИЦ С ПОМОЩЬЮ EASYOCR
# ====================================================

@router.message(or_f(Command("upload_photo"), F.text == "📷 Загрузить фото"))
async def start_upload_photo(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(UploadSchedulePhotoSG.waiting_for_photo)
    await message.answer(
        "📷 <b>Отправьте фотографию вашего расписания.</b>\n\n"
        "⚠️ <i>Обратите внимание:</i> Текущее расписание будет <u>полностью удалено</u> и заменено новыми данными!",
        parse_mode="HTML",
    )


@router.message(UploadSchedulePhotoSG.waiting_for_photo, F.photo)
async def process_schedule_photo(message: types.Message, state: FSMContext, bot):
    photo = message.photo[-1]
    photo_bytes = io.BytesIO()
    await bot.download(photo, destination=photo_bytes)
    photo_bytes.seek(0)

    try:
        image_bytes = photo_bytes.getvalue()
        results = reader.readtext(image_bytes, detail=1)
    except Exception:
        await message.answer("❌ Ошибка обработки фото с помощью EasyOCR.")
        await state.clear()
        return

    schedule_items = parse_schedule_text(results)

    if not schedule_items:
        await message.answer(
            "⚠️ Не удалось корректно привязать предметы к дням недели. Убедитесь, что заголовки дней недели (Пн, Вт, Ср...) хорошо видны на фото.",
            parse_mode="HTML",
        )
        await state.clear()
        return

    user_id = message.from_user.id

    async for session in db_manager.get_session():
        # Очищаем старое расписание перед записью нового
        await session.execute(delete(Schedule).where(Schedule.user_id == user_id))

        for item in schedule_items:
            new_schedule = Schedule(
                user_id=user_id,
                day_of_week=item["day_of_week"],
                start_time=item["start_time"],
                end_time=item["end_time"],
                title=item["title"],
            )
            session.add(new_schedule)

        await session.commit()

    await state.clear()
    await message.answer(
        f"✅ <b>Расписание успешно распознано!</b>\n"
        f"Добавлено уроков: <b>{len(schedule_items)}</b>.",
        parse_mode="HTML",
    )