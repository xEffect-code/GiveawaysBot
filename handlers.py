import json
from aiogram import Bot, Router, types
from aiogram.filters import Command, StateFilter
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, ContentType, Message
from aiogram.fsm.context import FSMContext
from config import ADMIN_CHAT_ID, CHANNEL_ID, ADMIN_ID
from fsm_states import BuySticker, Application, AdminPanel
from settings import get_settings, update_settings
from config import CHANNEL_LINK

router = Router()

pending_requests = {}  # message_id заявки: user_id

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
        f" 2. Отсканируй QR-код ниже\n"
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

@router.message(StateFilter(Application.waiting_photo))
async def process_photo(message: types.Message, state: FSMContext, bot: Bot):
    file_id = None

    if message.content_type == ContentType.PHOTO:
        file_id = message.photo[-1].file_id
        mime = "image/photo"
    elif message.content_type == ContentType.DOCUMENT:
        mime = message.document.mime_type
        if mime in ("application/pdf", "image/jpeg", "image/png", "image/jpg", "image/webp"):
            file_id = message.document.file_id
        else:
            await message.answer("❗Пожалуйста, отправьте изображение (jpeg, png, webp) или PDF-файл.")
            return
    else:
        await message.answer("❗Пожалуйста, отправьте изображение (фото) или PDF-файл.")
        return

    data = await state.get_data()
    qty = data['qty']

    text = (
        f"🆕 <b>Новая заявка</b>\n\n"
        f"👤 {data['fio']}\n"
        f"📱 {data['phone']}\n"
        f"📦 {qty} стикеров\n"
        f"🖼 Фото/чек:"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data="approve"),
         InlineKeyboardButton(text="❌ Отклонить", callback_data="reject")]
    ])

    sent = None
    if message.content_type == ContentType.PHOTO or (message.content_type == ContentType.DOCUMENT and mime.startswith("image/")):
        sent = await bot.send_photo(chat_id=ADMIN_CHAT_ID, photo=file_id, caption=text, parse_mode="HTML", reply_markup=kb)
    elif message.content_type == ContentType.DOCUMENT and mime == "application/pdf":
        sent = await bot.send_document(chat_id=ADMIN_CHAT_ID, document=file_id, caption=text, parse_mode="HTML", reply_markup=kb)

    if sent:
        pending_requests[sent.message_id] = message.from_user.id

    await message.answer(
        "✅ Ваша заявка на участие в розыгрыше отправлена!\n"
        "Мы уже проверяем вашу оплату. Если вы всё сделали правильно — билеты скоро будут у вас! 🎟✨\n\n"
        "⏳ В связи с оплатой банкинга и сверкой оплаты подтверждение может занять до 24 часов — пожалуйста, следите за сообщением бота и наберитесь немного терпения.\n\n"
        "📩 Как только платёж будет проверен, бот автоматически пришлёт вам информацию для участия в розыгрыше! 🎉\n\n"
        "❗Если у вас возникли трудности или вы не уверены, что всё прошло корректно — пожалуйста, свяжитесь с администратором:\n"
        "@CuttySark_81\n\n"
        "Спасибо, что участвуете! Удачи! 🍀"
    )
    await state.clear()

@router.callback_query(lambda c: c.data in ("approve", "reject"))
async def handle_decision(callback: CallbackQuery, bot: Bot):
    user_id = pending_requests.get(callback.message.message_id)
    if not user_id:
        await callback.answer("❗ Пользователь не найден.")
        return

    # Получаем username пользователя
    try:
        chat_member = await bot.get_chat_member(user_id=user_id, chat_id=user_id)
        username = chat_member.user.username
        if username:
            user_display = f"@{username}"
        else:
            user_display = f"id{user_id}"
    except Exception:
        user_display = f"id{user_id}"

    # Удаляем кнопки под исходной заявкой
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass

    buy_more_kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Купить ещё стикеры", callback_data="start_buy")]]
    )

    if callback.data == "approve":
        msg = (
            "✅ Вы все сделали правильно, спасибо!\n"
            "Ваша заявка подтверждена ✅\n\n"
            "🎟️ Вы добавлены в список на проведение розыгрыша, свой присвоенный номер билета вы можете найти в таблице👇\n\n"
            "https://docs.google.com/spreadsheets/d/1PvxOM2ZCqSKT8djc_3xy5RlE0mMIKKSa-7V2ZwuwYSI/edit?usp=drivesdk\n\n"
            "🍀 Желаем удачи в розыгрыше!\n\n"
            "👇 Хотите увеличить шансы?\n"
            "Вы можете приобрести ещё стикеры, гоу 👇"
        )
        await bot.send_message(user_id, msg, reply_markup=buy_more_kb)
        await bot.send_message(
            ADMIN_CHAT_ID,
            f"✅ Заявка пользователя {user_display} подтверждена",
            reply_to_message_id=callback.message.message_id
        )
    else:
        msg = (
            "❌ Ваша заявка отклонена.\n\n"
            "❗️Возможно, вы допустили ошибку при заполнении данных — наш оператор не нашёл вашего платежа.\n\n"
            "💸 Если вы оформили заявку ошибочно, нажмите на кнопку ниже и создайте новую.\n\n"
            "🤝 Если вы уверены, что всё сделали правильно, и считаете что заявка отклонена по ошибке — пожалуйста, свяжитесь с нашим администратором @CuttySark_81"
        )
        await bot.send_message(user_id, msg, reply_markup=buy_more_kb)
        await bot.send_message(
            ADMIN_CHAT_ID,
            f"❌ Заявка пользователя {user_display} отклонена",
            reply_to_message_id=callback.message.message_id
        )

    await callback.answer("Готово.")

# ---------------------------
# БЛОКИРОВКА ЛЮБЫХ ЛИЧНЫХ СООБЩЕНИЙ ВНЕ СЦЕНАРИЯ (СТРОГО В КОНЦЕ ФАЙЛА)
# ---------------------------
@router.message(StateFilter(None))
async def block_any_message(message: types.Message, state: FSMContext):
    if message.text and message.text.startswith('/'):
        return
    if message.from_user.id == ADMIN_ID:
        return
    pass
