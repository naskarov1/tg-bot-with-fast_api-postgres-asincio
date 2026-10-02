from aiogram.fsm.state import State, StatesGroup

class EditScheduleSG(StatesGroup):
    waiting_for_new_title = State()
    waiting_for_new_time = State()

class EditHomeworkSG(StatesGroup):
    waiting_for_new_text = State()

class AddScheduleSG(StatesGroup):
    title = State()
    day_of_week = State()
    time_range = State()
    remind_offset = State()


class AddHomeworkSG(StatesGroup):
    select_schedule = State()
    text = State()
    due_date = State()