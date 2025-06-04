import json
import uuid
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command, StateFilter
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, ContentType, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from config import ADMIN_CHAT_ID, CHANNEL_ID
from fsm_states import BuySticker, Application
from settings import get_settings
from support_status import is_support_open
from config import ADMIN_ID

dp = Dispatcher(storage=MemoryStorage())
ack_messages = {}
code_to_user = {}

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    invite_link = f"https://t.me/c/{str(CHANNEL_ID)[4:]}/"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Подписаться", url=invite_link)],
        [InlineKeyboardButton(text="Проверить подписку", callback_data="check_sub")]
    ])
    await message.answer("Привет! Чтобы участвовать в розыгрыше, подпишись на канал и нажми «Проверить подписку».", reply_markup=kb)

@dp.callback_query(lambda c: c.data == "check_sub")
async def check_subscription(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        if member.status in ("member", "creator", "administrator"):
            kb_buy = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Купить стикер", callback_data="start_buy")]
            ])
            await callback.message.answer("✅ Подписка подтверждена! Выберите действие:", reply_markup=kb_buy)
        else:
            await callback.message.answer("❗ Похоже, вы не подписаны.")
    except Exception:
        await callback.message.answer("⚠ Не удалось проверить подписку. Попробуйте позже.")
    await callback.answer()

@dp.callback_query(lambda c: c.data == "start_buy")
async def start_buy_sticker(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    price = get_settings()["price_per_ticket"]
    await callback.message.answer(f"📋 Напишите, сколько стикеров вы хотите купить (числом). Цена одного — {price:.2f} руб.")
    await state.set_state(BuySticker.waiting_qty)

@dp.message(StateFilter(BuySticker.waiting_qty))
async def process_qty(message: types.Message, state: FSMContext):
    text = message.text.strip()
    if not text.isdigit() or int(text) <= 0:
        await message.answer("❗ Введите корректное число.")
        return
    qty = int(text)
    await state.update_data(qty=qty)
    settings = get_settings()
    total = qty * settings["price_per_ticket"]
    if settings["payment_image_file_id"]:
        await message.answer_photo(settings["payment_image_file_id"])
    await message.answer(f"📌 Для покупки {qty} стикеров оплатите сумму: *{total:.2f} руб.*\n\n🔗 Ссылка: https://example.com/pay?amount={total:.2f}", parse_mode="Markdown")
    await message.answer("✏ Укажите ваше ФИО:")
    await state.set_state(Application.waiting_fio)

@dp.message(StateFilter(Application.waiting_fio))
async def process_fio(message: types.Message, state: FSMContext):
    if not message.text:
        await message.answer("❗ Пожалуйста, отправьте ваше ФИО текстом.")
        return
    fio = message.text.strip()
    if len(fio.split()) < 2:
        await message.answer("Укажите имя и фамилию.")
        return
    await state.update_data(fio=fio)
    await message.answer("📱 Укажите номер телефона:")
    await state.set_state(Application.waiting_phone)

@dp.message(StateFilter(Application.waiting_phone))
async def process_phone(message: types.Message, state: FSMContext):
    if not message.text:
        await message.answer("❗ Пожалуйста, отправьте номер телефона текстом.")
        return
    phone = message.text.strip()
    if not (phone.startswith("+") and phone[1:].isdigit()):
        await message.answer("Неверный формат телефона.")
        return
    await state.update_data(phone=phone)
    await message.answer("📸 Пришлите скрин или фото чека:")
    await state.set_state(Application.waiting_photo)

@dp.message(StateFilter(Application.waiting_photo), lambda m: m.content_type in (ContentType.PHOTO, ContentType.DOCUMENT))
async def process_photo(message: types.Message, state: FSMContext, bot: Bot):
    file_id = message.photo[-1].file_id if message.photo else message.document.file_id
    data = await state.get_data()
    code = uuid.uuid4().hex[:8].upper()
    code_to_user[code] = message.from_user.id
    ack_messages[message.from_user.id] = code
    text = f"🎟 *Новая заявка #{code}*\n\n👤 {data['fio']}\n📱 {data['phone']}\n📦 {data['qty']} стикеров\n🖼 Фото чека:"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"approve:{code}"),
         InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject:{code}")]
    ])
    await bot.send_photo(chat_id=ADMIN_CHAT_ID, photo=file_id, caption=text, parse_mode="Markdown", reply_markup=kb)
    await message.answer("✅ Ваша заявка отправлена. Ожидайте подтверждение.")
    await state.clear()

@dp.callback_query(lambda c: c.data.startswith("approve:") or c.data.startswith("reject:"))
async def handle_decision(callback: CallbackQuery, bot: Bot):
    action, code = callback.data.split(":")
    user_id = code_to_user.get(code)
    if not user_id:
        await callback.answer("❗ Пользователь не найден.")
        return

    if action == "approve":
        msg = f"✅ Ваша заявка *одобрена!* (номер: #{code})"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Купить ещё стикеры", callback_data="start_buy")]
        ])
        await bot.send_message(user_id, msg, parse_mode="Markdown", reply_markup=kb)
    else:
        msg = "❌ Ваша заявка *отклонена!*"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Связь с менеджером", callback_data=f"support:{code}")]
        ])
        await bot.send_message(user_id, msg, parse_mode="Markdown", reply_markup=kb)

    await callback.answer("Готово.")

# ---------------------------
# БЛОКИРОВКА ЛЮБЫХ ЛИЧНЫХ СООБЩЕНИЙ ВНЕ СЦЕНАРИЯ
# ---------------------------
@dp.message(StateFilter(None))
async def block_any_message(message: types.Message, state: FSMContext):
    # Разрешаем писать в поддержку, если открыто support окно
    if is_support_open(message.from_user.id):
        return
    # Разрешаем администратору любые сообщения
    if message.from_user.id == ADMIN_ID:
        return
    # Всё остальное блокируем (никаких ответов, сообщения не отправляются менеджерам)
    pass
