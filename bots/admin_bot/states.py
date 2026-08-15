from aiogram.fsm.state import State, StatesGroup


class AddPresetStates(StatesGroup):
    id = State()
    title = State()
    prompt_template = State()
    category = State()
    icon = State()
    target_bot_id = State()
