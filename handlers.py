import json
from aiogram import Bot, Router, types
from aiogram.filters import CommandStart, StateFilter
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, ContentType, Message
from aiogram.fsm.context import FSMContext
from config import ADMIN_CHAT_ID, CHANNEL_ID, ADMIN_ID, CHANNEL_LINK
from fsm_states import BuySticker, Application
from settings import get_settings
import referrals

router = Router()

pending_requests = {}  # message_id заявки: user_id


def get_users():
    try:
        with open("users.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


@router.message(CommandStart())
async def cmd_start(message: Message, command):
    # Сохраняем связь при /start (без зачёта)
    args = command.args or ""
    if referrals.is_active() and args.startswith("ref_"):
        try:
            referrer_id = int(args.split("_", 1)[1])
        except ValueError:
            referrer_id = None

        user_key = str(message.from_user.id)
        data = referrals.load_data()
        if referrer_id and referrer_id != message.from_user.id:
            if user_key not in data["users"]:
                data["users"][user_key] = {"referrer": referrer_id, "counted": False}
                referrals.save_data(data)

    # Регистрируем пользователя для рассылок
    user_id = message.from_user.id
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
        [InlineKeyboardButton(text="✍Подписаться на канал", url=CHANNEL_LINK)],
        [InlineKeyboardButton(text="‼Проверить подписку", callback_data="check_sub")],
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
            # Зачёт реферала только после подтверждения подписки
            data = referrals.load_data()
            threshold = data.get("threshold", 3)
            active = data.get("active", True)

            user_key = str(user_id)
            user_data = data["users"].get(user_key)
            if user_data and not user_data.get("counted", False):
                referrer_id = int(user_data["referrer"])
                ref_key = str(referrer_id)
                ref_info = data["referrers"].setdefault(
                    ref_key, {"referred": [], "tickets": [], "round_count": 0}
                )

                # Исторический учёт (вообще по проекту)
                if user_id not in ref_info["referred"]:
                    ref_info["referred"].append(user_id)

                # В текущем розыгрыше считаем только если он активен
                if active:
                    ref_info["round_count"] = int(ref_info.get("round_count", 0)) + 1

                    # Оповещение рефереру о новом реферале
                    try:
                        progress = ref_info["round_count"] % threshold
                        remain = threshold - progress if progress != 0 else 0
                        await bot.send_message(
                            referrer_id,
                            (
                                "👥 У вас новый реферал!\n"
                                f"Прогресс текущего розыгрыша: {ref_info['round_count']}/{threshold}.\n"
                                f"{'До билета осталось: ' + str(remain) if remain else 'Сейчас получите билет!'}"
                            )
                        )
                    except Exception:
                        pass

                    # Билет каждые threshold
                    if threshold > 0 and (ref_info["round_count"] % threshold == 0):
                        code = referrals.generate_unique_code(data)
                        ref_info["tickets"].append(code)

                        # Пользователю (рефереру)
                        try:
                            await bot.send_message(
                                referrer_id,
                                (
                                    "🎁 Поздравляем! Вы выполнили условия и получили бесплатный билет!\n"
                                    f"Ваш код: <b>{code}</b>\n\n"
                                    "Сохраните его — по этим кодам будет проводиться розыгрыш."
                                ),
                                parse_mode="HTML"
                            )
                        except Exception:
                            pass

                        # Админу
                        try:
                            ref_chat = await bot.get_chat(referrer_id)
                            ref_name = f"@{ref_chat.username}" if ref_chat.username else (ref_chat.full_name or f"id{referrer_id}")
                        except Exception:
                            ref_name = f"id{referrer_id}"
                        try:
                            await bot.send_message(
                                ADMIN_CHAT_ID,
                                f"🎟 Выдан бесплатный билет {ref_name} — код: <b>{code}</b> (порог {threshold})",
                                parse_mode="HTML"
                            )
                        except Exception:
                            pass

                # Помечаем приглашённого как учтённого (чтобы не накрутить)
                data["users"][user_key]["counted"] = True
                referrals.save_data(data)

            kb_buy = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🎟Купить стикер", callback_data="start_buy")],
                [InlineKeyboardButton(text="🤝Реферальная ссылка для друга", callback_data="referral_info")],
            ])
            await callback.message.answer(
                "✅ Подписка успешно подтверждена! Спасибо, что с нами! 🤗 Теперь ты можешь принять участие в розыгрыше и выиграть крутые призы! 🎁✨\n\n"
                "🎟 Чтобы участвовать — купи стикеры (они же билеты на участие в розыгрыше)!\n"
                "Чем больше стикеров — тем выше шанс на победу! 🔥\n\n"
                "🤝 Раздел «РЕФЕРАЛЬНАЯ СИСТЕМА»\n"
                "Делитесь своей реферальной ссылкой с друзьями, получайте бесплатные билеты за приглашения и участвуйте в специальных розыгрышах для активных участников!\n\n"
                "Удачи в розыгрыше! 🍀 Мы верим, именно ты станешь победителем! 🏆\n\n"
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
async def process_qty(message: Message, state: FSMContext):
    text = message.text.strip()
    if not text.isdigit() or int(text) <= 0:
        await message.answer("❗ Введите корректное число.")
        return
    qty = int(text)
    await state.update_data(qty=qty)
    settings = get_settings()
    total = qty * settings["price_per_ticket"]
    if settings.get("payment_image_file_id"):
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
async def process_fio(message: Message, state: FSMContext):
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
async def process_phone(message: Message, state: FSMContext):
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
async def process_photo(message: Message, state: FSMContext, bot: Bot):
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
    qty = data.get('qty')
    text = (
        f"🆕 <b>Новая заявка</b>\n\n"
        f"👤 {data.get('fio')}\n"
        f"📱 {data.get('phone')}\n"
        f"📦 {qty} стикеров\n"
        f"🖼 Фото/чек:"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data="approve"),
         InlineKeyboardButton(text="❌ Отклонить", callback_data="reject")]
    ])
    sent = None
    if file_id and (message.content_type == ContentType.PHOTO or (message.content_type == ContentType.DOCUMENT and mime.startswith("image/"))):
        sent = await bot.send_photo(chat_id=ADMIN_CHAT_ID, photo=file_id, caption=text, parse_mode="HTML", reply_markup=kb)
    elif file_id and message.content_type == ContentType.DOCUMENT and mime == "application/pdf":
        sent = await bot.send_document(chat_id=ADMIN_CHAT_ID, document=file_id, caption=text, parse_mode="HTML", reply_markup=kb)
    if sent:
        pending_requests[sent.message_id] = message.from_user.id
    await message.answer(
        "✅ Ваша заявка на участие в розыгрыше отправлена!\n"
        "Мы уже проверяем вашу оплату. Если вы всё сделали правильно — билеты скоро будут у вас! 🎟✨\n\n"
        "⏳ В связи с оплатой банкинга и сверкой оплаты подтверждение может занять до 24 часов — пожалуйста, следите за сообщением бота и наберитесь немного терпения.\n\n"
        "📩 Как только платёж будет проверен, бот автоматически пришлёт вам информацию для участия в розыгрыше! 🎉\n\n"
        "❗Если у вас возникли трудности или вы не уверены, что всё прошло корректно — пожалуйста, свяжитесь с администратором:\n"
       "@CuttySark_81"
    )
    await state.clear()


@router.callback_query(lambda c: c.data == "referral_info")
async def referral_info(callback: CallbackQuery):
    user_key = str(callback.from_user.id)
    data = referrals.load_data()
    ref_info = data.get("referrers", {}).get(user_key, {"referred": [], "tickets": [], "round_count": 0})
    total_referred = len(ref_info.get("referred", []))
    tickets = [str(x) for x in ref_info.get("tickets", [])]
    me = await callback.bot.get_me()
    link = f"https://t.me/{me.username}?start=ref_{callback.from_user.id}"
    text = (
        f"📊 <b>Ваша реферальная статистика</b>\n\n"
        "🚀 Приглашай друзей и получай бесплатные билеты для участия в специальных розыгрышах, которые мы проводим регулярно — и абсолютно бесплатно!\n"
        "Чем больше друзей — тем больше билетов и выше шанс забрать крутые призы! 🎁\n\n"
        "‼️ Важно:\n"
        "1️⃣ Количество друзей, необходимых для одного билета, может отличаться в зависимости от условий текущего розыгрыша.\n"
        "2️⃣ Чтобы друг засчитался, он должен активировать бота и подписаться на наш канал — только после этого он отобразится в вашей статистике.\n\n"
        f"👥 Приглашено: <b>{total_referred}</b>\n"
        f"🎫 Получено бесплатных билетов: <b>{len(tickets)}</b>\n"
    )
    if tickets:
        text += "Номера билетов: " + ", ".join(tickets) + "\n\n"
    text += f"🔗 Ваша ссылка: {link}"
    await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()


@router.callback_query(lambda c: c.data in ("approve", "reject"))
async def handle_decision(callback: CallbackQuery, bot: Bot):
    user_id = pending_requests.get(callback.message.message_id)
    if not user_id:
        await callback.answer("❗ Пользователь не найден.")
        return

    try:
        chat = await bot.get_chat(user_id)
        user_display = f"@{chat.username}" if chat.username else (chat.full_name or f"id{user_id}")
    except Exception:
        user_display = f"id{user_id}"

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
