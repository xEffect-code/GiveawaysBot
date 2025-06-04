from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from fsm_states import AdminPanel
from config import ADMIN_ID
from settings import get_settings, update_settings

router = Router()

@router.message(Command("admin"))
async def admin_panel(message: Message):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("❌ Доступ запрещён")
    settings = get_settings()
    price = settings.get("price_per_ticket", "не задано")
    photo = settings.get("payment_image_file_id", "не загружено")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📌 Изменить цену билета", callback_data="admin_change_price")],
        [InlineKeyboardButton(text="🖼 Загрузить фото оплаты", callback_data="admin_change_image")],
        [InlineKeyboardButton(text="📄 Посмотреть текущие настройки", callback_data="admin_view_settings")]
    ])
    text = (
        f"🔧 <b>Админ-панель</b>\n\n"
        f"💵 Цена билета: <b>{price}</b> руб.\n"
        f"🖼 Фото для оплаты: <code>{photo}</code>"
    )
    await message.answer(text, reply_markup=kb, parse_mode="HTML")

@router.callback_query(F.data == "admin_view_settings")
async def view_settings(callback: CallbackQuery):
    settings = get_settings()
    price = settings.get("price_per_ticket", "не задано")
    photo = settings.get("payment_image_file_id", "не загружено")
    text = (
        f"💵 Цена билета: <b>{price}</b> руб.\n"
        f"🖼 Фото для оплаты: <code>{photo}</code>"
    )
    await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "admin_change_price")
async def change_price(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите новую цену билета (например, 1000):")
    await state.set_state(AdminPanel.waiting_new_price)
    await callback.answer()

@router.message(AdminPanel.waiting_new_price)
async def set_price(message: Message, state: FSMContext):
    text = message.text.strip().replace(',', '.')
    try:
        price = float(text)
    except Exception:
        return await message.answer("❗ Введите число (например, 950)")
    update_settings({"price_per_ticket": price})
    await message.answer(f"✅ Цена обновлена: {price:.2f} руб.")
    await state.clear()

@router.callback_query(F.data == "admin_change_image")
async def change_image(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Пришлите фото, которое будет отображаться перед оплатой.")
    await state.set_state(AdminPanel.waiting_new_image)
    await callback.answer()

@router.message(AdminPanel.waiting_new_image, F.photo)
async def set_image(message: Message, state: FSMContext):
    file_id = message.photo[-1].file_id
    update_settings({"payment_image_file_id": file_id})
    await message.answer("✅ Фото для оплаты обновлено.")
    await state.clear()

@router.message(AdminPanel.waiting_new_image)
async def wrong_image(message: Message):
    await message.answer("❗ Пожалуйста, пришлите изображение.")
