from __future__ import annotations

import logging
from pathlib import Path

from telebot import TeleBot
from telebot.apihelper import ApiTelegramException

from bot.keyboards import SITE_URL, home_keyboard
from bot.media_store import get_home_photo_id, set_home_photo_id

log = logging.getLogger(__name__)

LOGO_PATH = Path(__file__).resolve().parent / "assets" / "br-logo-color.png"
if not LOGO_PATH.is_file():
    LOGO_PATH = Path(__file__).resolve().parent.parent / "br-logo-color.png"

BOT_NAME = "BR Infinite Compressor"
COMPANY_HTML = f'<a href="{SITE_URL}">BR Infinite Solutions</a>'

HOME_CAPTION = (
    f"<b>{BOT_NAME}</b>\n"
    f"by {COMPANY_HTML}\n\n"
    "Reduce images and PDFs to a size you choose — 200 KB, 300 KB, 500 KB, 1 MB, "
    "or a custom limit — while keeping as much quality as possible."
)

COMPRESSOR_TEXT = (
    "Please send an image or a PDF to continue.\n\n"
    "For the best quality, attach the file as a document rather than a compressed photo.\n"
    "You may use /cancel at any time to discard the current file."
)

_STALE_ID_MARKERS = (
    "wrong file identifier",
    "file identifier",
    "file is too big",
    "failed to get http url content",
)


def _is_stale_file_id(exc: BaseException) -> bool:
    text = str(exc).lower()
    return any(marker in text for marker in _STALE_ID_MARKERS)


def send_home(bot: TeleBot, chat_id: int) -> None:
    markup = home_keyboard()
    cached = get_home_photo_id()
    if cached:
        try:
            bot.send_photo(
                chat_id,
                cached,
                caption=HOME_CAPTION,
                parse_mode="HTML",
                reply_markup=markup,
            )
            log.info("sent home photo using cached file_id")
            return
        except ApiTelegramException as exc:
            if not _is_stale_file_id(exc):
                raise
            log.warning("cached home photo file_id was rejected; uploading the logo once more")
            set_home_photo_id(None)

    if not LOGO_PATH.is_file():
        bot.send_message(
            chat_id,
            HOME_CAPTION,
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=markup,
        )
        return

    with LOGO_PATH.open("rb") as photo:
        sent = bot.send_photo(
            chat_id,
            photo,
            caption=HOME_CAPTION,
            parse_mode="HTML",
            reply_markup=markup,
        )
    if sent.photo:
        set_home_photo_id(sent.photo[-1].file_id)
        log.info("uploaded home logo once and stored file_id")
