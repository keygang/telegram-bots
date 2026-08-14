from aiogram.fsm.state import State, StatesGroup


class GenerationStates(StatesGroup):
    """
    Finite State Machine (FSM) states for media generation workflows.
    """
    selecting_preset = State()
    waiting_for_photo = State()
    entering_custom_prompt = State()
    generating = State()
