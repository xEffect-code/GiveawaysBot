import json
import uuid
from aiogram import Bot, Router, types, F
from aiogram.filters import Command, StateFilter
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, ContentType, Message
from aiogram.fsm.context import FSMContext
from config import ADMIN_CHAT_ID, CHANNEL_ID, ADMIN_ID
from fsm_states import BuySticker, Application, AdminPanel
from settings import get_settings, update_settings
from support_status import is_support_open
from config import CHANNEL_LINK

router = Router()

ack_messages = {}
code_to_user = {}

def get_users():
    try:
        with open("users.json", "r", encoding="utf-8") as f:
            users = json.load(f)
        return users
    except Exception:
        return []

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id

    # --- Добавляем пользователя в users.json, если его там ещё нет
    try:
        with open("users.json", "r", encoding="utf-8") as f:
            users = json.load(f)
    except Exception:
        users = []

    if user_id not in users:
        users.append(user_id)
        with open("users.json", "w", encoding="utf-8") as f:
            json.dump(users, f, ensure_ascii=False, indent=2)

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Подписаться на канал", url=CHANNEL_LINK)],
        [InlineKeyboardButton(text="Проверить подписку", callback_data="check_sub")]
    ])
    await message.answer(
        "Привет! Чтобы участвовать в розыгрыше, подпишись на канал и нажми «Проверить подписку».",
        reply_markup=kb
    )

# --- АДМИН-ПАНЕЛЬ ---

@router.message(Command("admin"))
async def admin_panel(message: Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return await message.answer("❌ Доступ запрещён")
    settings = get_settings()
    price = settings.get("price_per_ticket", "не задано")
    photo = settings.get("payment_image_file_id", "не загружено")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📌 Изменить цену билета", callback_data="admin_change_price")],
        [InlineKeyboardButton(text="🖼 Загрузить фото оплаты", callback_data="admin_change_image")],
        [InlineKeyboardButton(text="📄 Посмотреть текущие настройки", callback_data="admin_view_settings")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")]
    ])
    text = (
        f"🔧 <b>Админ-панель</b>\n\n"
        f"💵 Цена билета: <b>{price}</b> руб.\n"
        f"🖼 Фото для оплаты: <code>{photo}</code>"
    )
    await message.answer(text, reply_markup=kb, parse_mode="HTML")

@router.callback_query(lambda c: c.data == "admin_view_settings")
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

@router.callback_query(lambda c: c.data == "admin_change_price")
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

@router.callback_query(lambda c: c.data == "admin_change_image")
async def change_image(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Пришлите фото, которое будет отображаться перед оплатой.")
    await state.set_state(AdminPanel.waiting_new_image)
    await callback.answer()

@router.message(AdminPanel.waiting_new_image, lambda m: m.photo is not None)
async def set_image(message: Message, state: FSMContext):
    file_id = message.photo[-1].file_id
    update_settings({"payment_image_file_id": file_id})
    await message.answer("✅ Фото для оплаты обновлено.")
    await state.clear()

@router.message(AdminPanel.waiting_new_image)
async def wrong_image(message: Message):
    await message.answer("❗ Пожалуйста, пришлите изображение.")

# --- РАССЫЛКА ---

@router.callback_query(lambda c: c.data == "admin_broadcast")
async def admin_broadcast(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "✉️ Пришлите текст, фото или видео для рассылки (можно с подписью).\n"
        "После отправки бот попросит подтвердить рассылку."
    )
    await state.set_state(AdminPanel.waiting_broadcast)
    await callback.answer()

@router.message(AdminPanel.waiting_broadcast, lambda m: m.photo is not None)
async def receive_broadcast_photo(message: Message, state: FSMContext):
    await state.update_data(
        broadcast_type="photo",
        file_id=message.photo[-1].file_id,
        caption=message.caption or ""
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_broadcast")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_broadcast")]
    ])
    await message.answer_photo(
        message.photo[-1].file_id,
        caption=message.caption or "(без подписи)",
        reply_markup=kb
    )
    await state.set_state(AdminPanel.confirm_broadcast)

@router.message(AdminPanel.waiting_broadcast, lambda m: m.video is not None)
async def receive_broadcast_video(message: Message, state: FSMContext):
    await state.update_data(
        broadcast_type="video",
        file_id=message.video.file_id,
        caption=message.caption or ""
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_broadcast")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_broadcast")]
    ])
    await message.answer_video(
        message.video.file_id,
        caption=message.caption or "(без подписи)",
        reply_markup=kb
    )
    await state.set_state(AdminPanel.confirm_broadcast)

@router.message(AdminPanel.waiting_broadcast)
async def receive_broadcast_text(message: Message, state: FSMContext):
    await state.update_data(
        broadcast_type="text",
        text=message.text
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_broadcast")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_broadcast")]
    ])
    await message.answer(
        f"Текст рассылки:\n\n{message.text}",
        reply_markup=kb
    )
    await state.set_state(AdminPanel.confirm_broadcast)

@router.callback_query(lambda c: c.data == "cancel_broadcast")
async def cancel_broadcast(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("❌ Рассылка отменена.")
    await callback.answer()

@router.callback_query(lambda c: c.data == "confirm_broadcast")
async def confirm_broadcast(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    users = get_users()
    success = 0
    failed = 0

    await callback.message.answer("🚀 Рассылка началась...")
    from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError

    for user_id in users:
        try:
            if data.get("broadcast_type") == "photo":
                await callback.bot.send_photo(
                    user_id, data["file_id"], caption=data.get("caption", "")
                )
            elif data.get("broadcast_type") == "video":
                await callback.bot.send_video(
                    user_id, data["file_id"], caption=data.get("caption", "")
                )
            elif data.get("broadcast_type") == "text":
                await callback.bot.send_message(
                    user_id, data["text"]
                )
            success += 1
        except (TelegramBadRequest, TelegramForbiddenError):
            failed += 1
        except Exception:
            failed += 1

    await callback.message.answer(f"✅ Рассылка завершена!\n\nУспешно: {success}\nНе отправлено: {failed}")
    await state.clear()
    await callback.answer()

# --- Остальная логика бота (оставь как было, ниже...)

# Здесь оставь твои остальные обработчики из этого файла!
# Например, проверки подписки, покупка билетов, отправка заявок и так далее
