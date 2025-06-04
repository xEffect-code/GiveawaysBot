import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN       = os.getenv("BOT_TOKEN")
ADMIN_ID        = int(os.getenv("ADMIN_ID", 0))
ADMIN_CHAT_ID   = int(os.getenv("ADMIN_CHAT_ID", 0))
CHANNEL_ID      = int(os.getenv("CHANNEL_ID", 0))
MANAGER_CHAT_ID = int(os.getenv("MANAGER_CHAT_ID", -4843389283))
