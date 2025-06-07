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

# --- ПРОВЕРКА ПОДПИСКИ ---

@router.callback_query(lambda c: c.data == "check_sub")
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

# --- КУПИТЬ СТИКЕР/ОФОРМЛЕНИЕ ЗАЯВКИ ---

@router.callback_query(lambda c: c.data == "start_buy")
async def start_buy_sticker(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    price = get_settings()["price_per_ticket"]
    await callback.message.answer(f"📋 Напишите, сколько стикеров вы хотите купить (числом). Цена одного — {price:.2f} руб.")
    await state.set_state(BuySticker.waiting_qty)

@router.message(StateFilter(BuySticker.waiting_qty))
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
    await message.answer("✏ Для получения номера билета, пожалуйста укажите ваше ФИО:")
    await state.set_state(Application.waiting_fio)

@router.message(StateFilter(Application.waiting_fio))
async def process_fio(message: types.Message, state: FSMContext):
    if not message.text:
        await message.answer("❗ Пожалуйста, отправьте ваше ФИО текстом.")
        return
    fio = message.text.strip()
    if len(fio.split()) < 2:
        await message.answer("Укажите имя и фамилию.")
        return
    await state.update_data(fio=fio)
    await message.answer("📱 Укажите номер телефона в формате +79999999999:")
    await state.set_state(Application.waiting_phone)

@router.message(StateFilter(Application.waiting_phone))
async def process_phone(message: types.Message, state: FSMContext):
    if not message.text:
        await message.answer("❗ Пожалуйста, отправьте номер телефона текстом.")
        return
    phone = message.text.strip()
    if not (phone.startswith("+") and phone[1:].isdigit()):
        await message.answer("Неверный формат телефона.")
        return
    await state.update_data(phone=phone)
    await message.answer("📸 Пришлите скрин или фото чека об оплате:")
    await state.set_state(Application.waiting_photo)

@router.message(StateFilter(Application.waiting_photo), lambda m: m.content_type in (ContentType.PHOTO, ContentType.DOCUMENT))
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
    await message.answer("✅ Ваша заявка заявка на участие в розыгрыше отправлена. Ожидайте подтверждение.")
    await state.clear()

# --- ОБРАБОТКА ЗАЯВОК (без кнопки "Связь с менеджером") ---

@router.callback_query(lambda c: c.data.startswith("approve:") or c.data.startswith("reject:"))
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
        await bot.send_message(user_id, msg, parse_mode="Markdown")

    await callback.answer("Готово.")

# ---------------------------
# БЛОКИРОВКА ЛЮБЫХ ЛИЧНЫХ СООБЩЕНИЙ ВНЕ СЦЕНАРИЯ (СТРОГО В КОНЦЕ ФАЙЛА)
# ---------------------------
@router.message(StateFilter(None))
async def block_any_message(message: types.Message, state: FSMContext):
    # Разрешаем команды (не блокируем сообщения, которые начинаются с '/')
    if message.text and message.text.startswith('/'):
        return
    # Разрешаем администратору любые сообщения
    if message.from_user.id == ADMIN_ID:
        return
    # Всё остальное блокируем
    pass
