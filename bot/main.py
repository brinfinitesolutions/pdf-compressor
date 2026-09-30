from __future__ import annotations

import logging
import os

from dotenv import load_dotenv
from telebot import TeleBot

from bot.handlers import register_handlers


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    load_dotenv()
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    if not token or token == "your-bot-token-from-botfather":
        raise SystemExit("Set TELEGRAM_BOT_TOKEN in .env (from @BotFather)")

    bot = TeleBot(token)
    register_handlers(bot)
    bot.infinity_polling(skip_pending=True, timeout=60, long_polling_timeout=60)


if __name__ == "__main__":
    main()
