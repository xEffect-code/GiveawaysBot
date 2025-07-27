from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto, InputMediaVideo
from aiogram.fsm.context import FSMContext
from fsm_states import AdminPanel
from config import ADMIN_ID
from settings import get_settings, update_settings
import referrals
from datetime import datetime
import random
import string

import json

router = Router()

def get_users():
    try:
        with open("users.json", "r", encoding="utf-8") as f:
            users = json.load(f)
        return users
    except Exception:
        return []

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
        [InlineKeyboardButton(text="📄 Посмотреть текущие настройки", callback_data="admin_view_settings")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="📈 Реферальная статистика", callback_data="admin_ref_stats")],
        [InlineKeyboardButton(text="⏸️ Приостановить реферальный розыгрыш", callback_data="admin_pause_ref")],
        [InlineKeyboardButton(text="▶️ Запустить новый реферальный розыгрыш", callback_data="admin_start_ref")]
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

# --- РАССЫЛКА ---

@router.callback_query(F.data == "admin_broadcast")
async def admin_broadcast(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer(
        "✉️ Пришлите текст, фото или видео для рассылки (можно с подписью).\n"
        "После отправки бот попросит подтвердить рассылку."
    )
    await state.set_state(AdminPanel.waiting_broadcast)
    await callback.answer()

@router.message(AdminPanel.waiting_broadcast, F.photo)
async def receive_broadcast_photo(message: Message, state: FSMContext):
    # Сохраняем file_id и подпись
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

@router.message(AdminPanel.waiting_broadcast, F.video)
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

@router.callback_query(F.data == "cancel_broadcast")
async def cancel_broadcast(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("❌ Рассылка отменена.")
    await callback.answer()

@router.callback_query(F.data == "confirm_broadcast")
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

@router.callback_query(F.data == "admin_ref_stats")
async def admin_ref_stats(callback: CallbackQuery):
    data = referrals.load_data()
    lines = []
    for ref_id, info in data["referrers"].items():
        lines.append(f"👤 {ref_id}: {len(info['referred'])} приг., {len(info['tickets'])} билетов")
    text = "📊 <b>Все реф. аккаунты</b>\n\n" + "\n".join(lines)
    await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "admin_pause_ref")
async def admin_pause_ref(callback: CallbackQuery):
    data = referrals.load_data()

    # считаем общее количество приглашённых и выданных билетов
    total_part = sum(len(v["referred"]) for v in data["referrers"].values())
    total_tix  = sum(len(v["tickets"])  for v in data["referrers"].values())

    # приостанавливаем розыгрыш и сохраняем в историю
    data["active"] = False
    data["history"].append({
        "action": "paused",
        "time": datetime.utcnow().isoformat(),
        "participants": total_part,
        "tickets": total_tix
    })
    referrals.save_data(data)

    # готовим список участников с «шестизначными» кодами
    lines = []
    for ref_id, info in data["referrers"].items():
        if not info["tickets"]:
            continue
        # получаем имя/username
        try:
            member = await callback.bot.get_chat_member(chat_id=int(ref_id), user_id=int(ref_id))
            username = f"@{member.user.username}" if member.user.username else member.user.full_name
        except:
            username = f"id{ref_id}"
        # генерируем по коду на каждый билет
        codes = [
            "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
            for _ in info["tickets"]
        ]
        lines.append(f"{username}: {', '.join(codes)}")

    detail_text = "\n".join(lines) or "— нет выданных билетов —"

    # отправляем результат админу
    await callback.message.answer(
        (
            f"⏸️ <b>Реферальный розыгрыш приостановлен</b>\n\n"
            f"👥 Всего приглашено: <b>{total_part}</b>\n"
            f"🎫 Выдано билетов: <b>{total_tix}</b>\n\n"
            f"<b>Участники и их коды:</b>\n"
            f"{detail_text}"
        ),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "admin_start_ref")
async def admin_start_ref(callback: CallbackQuery):
    data = referrals.load_data()
    data["active"] = True
    # чистим только выданные билеты, но сохраняем списки рефералов
    for info in data["referrers"].values():
        info["tickets"] = []
    data["history"].append({
        "action": "started",
        "time": datetime.utcnow().isoformat()
    })
    referrals.save_data(data)
    await callback.message.answer("▶️ Новый реферальный розыгрыш запущен. Счетчики билетов сброшены.")
    await callback.answer()

