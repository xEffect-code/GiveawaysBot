from aiogram.fsm.state import StatesGroup, State

class BuySticker(StatesGroup):
    waiting_qty = State()

class Application(StatesGroup):
    waiting_fio = State()
    waiting_phone = State()
    waiting_photo = State()

class AdminPanel(StatesGroup):
    waiting_new_price = State()
    waiting_new_image = State()
