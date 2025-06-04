from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from config import MANAGER_CHAT_ID
import json
from pathlib import Path
from support_status import is_support_open, set_support_open

router = Router()

MAP_PATH = Path("support_message_map.json")
USER_WARNED_PATH = Path("support_user_warned.json")  # для одноразового уведомления

def load_map():
    if MAP_PATH.exists():
        with open(MAP_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_map(data):
    with open(MAP_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def load_warned():
    if USER_WARNED_PATH.exists():
        with open(USER_WARNED_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_warned(data):
    with open(USER_WARNED_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

message_map = load_map()
user_warned = load_warned()

@router.callback_query(F.data.startswith("support:"))
async def start_support(callback: CallbackQuery):
    set_support_open(callback.from_user.id, True)
    user_warned.pop(str(callback.from_user.id), None)
    save_warned(user_warned)
    await callback.message.answer("✉ Напишите свой вопрос, менеджер скоро ответит.")
    await callback.answer()

@router.message(Command("testsend"))
async def test_send(message: Message):
    try:
        await message.bot.send_message(8069401781, "✅ Тест: это сообщение отправлено вручную")
    except Exception as e:
        await message.answer(f"❌ Ошибка при ручной отправке: {e}")

@router.message(lambda m: m.chat.type == "private")
async def forward_to_manager(message: Message):
    user_id = message.from_user.id
    if not is_support_open(user_id):
        # Отправлять сообщение только один раз за сессию — чтобы не раздражать пользователя
        if not user_warned.get(str(user_id)):
            await message.answer("Чтобы связаться с менеджером, нажмите кнопку \"Связь с менеджером\" в меню или после отклонения заявки.")
            user_warned[str(user_id)] = True
            save_warned(user_warned)
        return

    username = f"@{message.from_user.username}" if message.from_user.username else message.from_user.full_name
    header = f"👤 Пользователь ({username}) | ID: {user_id} пишет:"

    sent_msg = None
    if message.photo:
        file_id = message.photo[-1].file_id
        sent_msg = await message.bot.send_photo(MANAGER_CHAT_ID, file_id, caption=header)
    elif message.document:
        file_id = message.document.file_id
        sent_msg = await message.bot.send_document(MANAGER_CHAT_ID, file_id, caption=header)
    elif message.video:
        file_id = message.video.file_id
        sent_msg = await message.bot.send_video(MANAGER_CHAT_ID, file_id, caption=header)
    elif message.voice:
        file_id = message.voice.file_id
        sent_msg = await message.bot.send_voice(MANAGER_CHAT_ID, file_id, caption=header)
    else:
        sent_msg = await message.bot.send_message(MANAGER_CHAT_ID, f"{header}\n{message.text}")

    if sent_msg:
        message_map[str(sent_msg.message_id)] = user_id
        save_map(message_map)

    await message.answer("✅ Сообщение отправлено нашим менеджерам, ожидайте ответа.")

@router.message(lambda m: m.chat.id == MANAGER_CHAT_ID and m.reply_to_message is not None)
async def reply_to_user(message: Message):
    reply_msg = message.reply_to_message
    msg_id_str = str(reply_msg.message_id)
    target_id = message_map.get(msg_id_str)

    if not target_id:
        await message.reply("❗ Не найден user_id для этого сообщения.")
        return

    try:
        if message.text and not any([message.photo, message.document, message.voice, message.video]):
            await message.bot.send_message(
                target_id,
                f"💬 *Сообщение от менеджера:*\n{message.text}",
                parse_mode="Markdown"
            )
        elif message.photo:
            await message.bot.send_photo(
                target_id,
                message.photo[-1].file_id,
                caption="💬 Сообщение от менеджера (фото)"
            )
        elif message.document:
            await message.bot.send_document(
                target_id,
                message.document.file_id,
                caption="💬 Сообщение от менеджера (документ)"
            )
        elif message.voice:
            await message.bot.send_voice(
                target_id,
                message.voice.file_id,
                caption="💬 Сообщение от менеджера (voice)"
            )
        elif message.video:
            await message.bot.send_video(
                target_id,
                message.video.file_id,
                caption="💬 Сообщение от менеджера (видео)"
            )
        else:
            await message.reply("❗ Не удалось отправить сообщение: неизвестный тип.")

        await message.reply("✅ Ответ отправлен пользователю.")
    except Exception as e:
        await message.reply(f"❗ Ошибка при отправке пользователю: {e}")

# Команда для менеджеров: завершить чат (закрыть поддержку для пользователя)
@router.message(Command("endchat"))
async def end_chat(message: Message):
    if message.reply_to_message:
        reply_msg = message.reply_to_message
        msg_id_str = str(reply_msg.message_id)
        target_id = message_map.get(msg_id_str)
        if not target_id:
            await message.reply("❗ Не найден user_id для этого сообщения.")
            return
        set_support_open(target_id, False)
        await message.reply("❎ Чат с пользователем завершён. Теперь пользователь не может писать менеджеру.")
