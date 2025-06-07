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
user_codes = {}  # Новый словарь: code -> [codes]

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
        "🎉 Привет друг! \n"
        "Добро пожаловать в наш Rusinov&Dedyukhin бот розыгрышей! \n"
        "🎉 Здесь тебя ждут классные призы, удача и отличное настроение! 🥳\n\n"
        "🤝 Чтобы принять участие в розыгрыше и получать всю подробную информацию:\n"
        "👉 Подпишись на наш канал\n"
        "👉 Нажми кнопку «Проверить подписку»\n\n"
        "🚀 Не упусти шанс — призы уже ждут своих победителей! 🎁\n"
        "Удачи тебе! 🍀",
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
            await callback.message.answer(
                "✅ Подписка успешно подтверждена! Спасибо, что с нами! 🤗 Теперь ты можешь принять участие в розыгрыше и выиграть крутые призы! 🎁✨\n\n"
                "🎟 Чтобы участвовать — купи стикеры (они же билеты на участие в розыгрыше)!\n"
                "Чем больше стикеров — тем выше шанс на победу! 🔥\n\n"
                "📥 Нажми кнопку «Купить стикер» и введи, сколько штук хочешь приобрести.\n\n"
                "Удачи в розыгрыше! 🍀 Мы верим, именно ты станешь победителем! 🏆 \n\n"
                "❗️По интересующим вопросам: @CuttySark_81",
                reply_markup=kb_buy
            )
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
    await callback.message.answer(
        "📋 Укажите, сколько стикеров (они же билеты для участие в розыгрыше ) вы хотите приобрести — просто введите число.\n\n"
        f"💸 Стоимость одного стикера — {price:.2f} руб.\n\n"
        "🎟 Больше стикеров — больше шансов на победу! Не упусти свой шанс забрать приз! 🏆🎁\n\n"
        "Ждём твой выбор! ⬇️"
    )
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
    await message.answer(
        f"💳 Оплата стикеров для участия в розыгрыше\n\n"
        f"🎉 Отличный выбор! Осталось несколько простых действий:\n\n"
        f"Для покупки {qty} стикеров оплатите сумму {total:.0f} руб. 💸\n\n"
        f"📌 Как оплатить:\n"
        f" 1. Открой приложение своего банка 📱\n"
        f" 2. Отсканируй QR-код выше\n"
        f" 3. Введи сумму {total:.0f} руб. вручную, если не подставится автоматически\n"
        f" 4. Подтверди перевод ✅\n\n"
        f"🔗 Или воспользуйся ссылкой для оплаты:\n\n"
        f"🎟️ После оплаты вернитесь в бота и следуйте его сообщениям!\n"
        f"🔥 Желаем удачи! 🍀"
    )
    await message.answer(
        "📝 Если вы оплатили стикеры — сохраните, пожалуйста, чек!\n"
        "Для того чтобы получить ваши стикеры (билеты), мы должны проверить платёж.\n\n"
        "✍️ Пожалуйста, введите ваше ФИО:"
    )
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
    await message.answer(
        "📱 Укажите номер телефона в формате +79000000000:\n\n"
        "‼️ Пожалуйста, вводите действующий номер телефона👇\n\n"
        "🏆 Он нужен для проверки платежа и связи с вами в случае выигрыша"
    )
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
    await message.answer(
        "📸 Пожалуйста, пришлите скриншот или фото чека об оплате:\n\n"
        "‼️ Важно:\n"
        "🔹 Отправляйте только чек вашей оплаты.\n"
        "🔹 Не пересылайте чужие или неподтверждённые чеки — каждый платёж проверяется вручную и строго идентифицируется по ФИО и номеру телефона."
    )
    await state.set_state(Application.waiting_photo)

@router.message(StateFilter(Application.waiting_photo), lambda m: m.content_type in (ContentType.PHOTO, ContentType.DOCUMENT))
async def process_photo(message: types.Message, state: FSMContext, bot: Bot):
    file_id = message.photo[-1].file_id if message.photo else message.document.file_id
    data = await state.get_data()
    qty = data['qty']
    codes = [uuid.uuid4().hex[:8].upper() for _ in range(qty)]
    await state.update_data(codes=codes)
    code_to_user[codes[0]] = message.from_user.id
    ack_messages[message.from_user.id] = codes[0]
    user_codes[codes[0]] = codes  # Сохраняем список кодов для этой заявки

    codes_str = "\n".join(f"`{c}`" for c in codes)
    text = (
        f"🎟 *Новая заявка*\n\n"
        f"👤 {data['fio']}\n"
        f"📱 {data['phone']}\n"
        f"📦 {qty} стикеров\n"
        f"🆔 Коды:\n{codes_str}\n"
        f"🖼 Фото чека:"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"approve:{codes[0]}"),
         InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject:{codes[0]}")]
    ])
    await bot.send_photo(chat_id=ADMIN_CHAT_ID, photo=file_id, caption=text, parse_mode="Markdown", reply_markup=kb)
    await message.answer(
        "✅ Ваша заявка на участие в розыгрыше отправлена!\n"
        "Мы уже проверяем вашу оплату. Если вы всё сделали правильно — билеты скоро будут у вас! 🎟✨\n\n"
        "⏳ В связи с оплатой банкинга и сверкой оплаты подтверждение может занять до 24 часов — пожалуйста, следите за сообщением бота и наберитесь немного терпения.\n\n"
        "📩 Как только платёж будет проверен, бот автоматически пришлёт вам сгенерированные билеты для участия в розыгрыше! 🎉\n\n"
        "❗Если у вас возникли трудности или вы не уверены, что всё прошло корректно — пожалуйста, свяжитесь с администратором:\n"
        "@CuttySark_81\n\n"
        "Спасибо, что участвуете! Удачи! 🍀"
    )
    await state.clear()

# --- ОБРАБОТКА ЗАЯВОК (без кнопки "Связь с менеджером", с выдачей всех кодов) ---

@router.callback_query(lambda c: c.data.startswith("approve:") or c.data.startswith("reject:"))
async def handle_decision(callback: CallbackQuery, bot: Bot):
    action, code = callback.data.split(":")
    user_id = code_to_user.get(code)
    if not user_id:
        await callback.answer("❗ Пользователь не найден.")
        return

    if action == "approve":
        codes_list = user_codes.get(code, [code])
        codes_str = "\n".join(f"`{c}`" for c in codes_list)
        msg = f"✅ Ваша заявка *одобрена!*\n\nВаши коды:\n{codes_str}"
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
