from aiogram.fsm.state import State, StatesGroup


class AddScheduleSG(StatesGroup):
    title = State()
    day_of_week = State()
    time_range = State()
    remind_offset = State()


class AddHomeworkSG(StatesGroup):
    select_schedule = State()
    text = State()
    due_date = State()