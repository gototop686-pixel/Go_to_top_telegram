from aiogram.fsm.state import State, StatesGroup

class SalesFunnel(StatesGroup):
    waiting_for_name = State()
    waiting_for_article = State()
    waiting_for_box_qty = State()
    waiting_for_planned_qty = State()

class SupportMode(StatesGroup):
    asking_question = State()

class ManagerChat(StatesGroup):
    in_chat = State()
