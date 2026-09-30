from __future__ import annotations

import logging
import re
import shutil
import tempfile
from pathlib import Path

import img2pdf
from telebot import TeleBot
from telebot.types import CallbackQuery, InlineKeyboardMarkup, Message

from bot.compress_image import compress_image
from bot.compress_pdf import compress_pdf
from bot.keyboards import SIZE_BYTES, custom_keyboard, format_keyboard, size_keyboard, website_keyboard
from bot import session as sessions
from bot.session import Session
from bot.welcome import BOT_NAME, COMPANY_HTML, COMPRESSOR_TEXT, send_home
from bot import usage as quotas

IMAGE_MIMES = {
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
    "image/gif",
}
IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff"}
WORKDIR = Path(tempfile.gettempdir()) / "pdf-compressor"
CUSTOM_NUMBER = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*(?:kb|k|mb|m)?\s*$", re.IGNORECASE)
COMPRESSING_TEXT = "Compressing… this may take a moment."
LIMIT_MESSAGE = (
    "You have reached the daily limit of 5 files or 10 MB for this service.\n\n"
    f"For a higher allowance, please contact {COMPANY_HTML}."
)
log = logging.getLogger(__name__)


def _user_dir(user_id: int) -> Path:
    path = WORKDIR / str(user_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _reset_files(user_id: int) -> None:
    path = _user_dir(user_id)
    shutil.rmtree(path, ignore_errors=True)
    path.mkdir(parents=True, exist_ok=True)


def _fmt_size(n: int) -> str:
    if n >= 1024 * 1024:
        return f"{n / (1024 * 1024):.2f} MB"
    if n >= 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n} B"


def _stem(name: str) -> str:
    return Path(name).stem or "file"


def _image_to_pdf(image_path: str, dest: Path) -> int:
    dest.write_bytes(img2pdf.convert(image_path))
    return dest.stat().st_size


def _delete(bot: TeleBot, chat_id: int, message_id: int | None) -> None:
    if not message_id:
        return
    try:
        bot.delete_message(chat_id, message_id)
    except Exception:
        pass


def _size_prompt(sess: Session) -> str:
    return (
        f"Received {sess.original_name} ({_fmt_size(sess.original_size)}). "
        "What maximum size would you like?"
    )


def _custom_prompt(unit: str) -> str:
    if unit == "mb":
        return "Please send the size in MB as a number, for example 1.5"
    return "Please send the size in KB as a number, for example 250"


def _edit_prompt(bot: TeleBot, sess: Session, text: str, markup=None) -> None:
    if markup is None:
        markup = InlineKeyboardMarkup()
    try:
        bot.edit_message_text(
            text,
            sess.chat_id,
            sess.prompt_message_id,
            reply_markup=markup,
        )
        return
    except Exception as exc:
        if "not modified" in str(exc).lower():
            return
        log.debug("edit prompt failed; sending a replacement", exc_info=True)
    try:
        sent = bot.send_message(
            sess.chat_id,
            text,
            reply_to_message_id=sess.source_message_id,
            reply_markup=markup if markup.keyboard else None,
            allow_sending_without_reply=True,
        )
        sess.prompt_message_id = sent.message_id
        sessions.put(sess)
    except Exception:
        log.exception("could not resend prompt")


def _result_caption(sess: Session) -> str:
    target = sess.target_bytes or 0
    compressed = sess.compressed_size or 0
    lines = [
        f"Original: {_fmt_size(sess.original_size)}",
        f"Compressed: {_fmt_size(compressed)}",
        f"Target: under {_fmt_size(target)}",
    ]
    if not sess.under_target:
        lines.append("This is the smallest result we could produce while staying as close as possible to your target.")
    lines.extend(
        [
            "",
            f"Thank you for using {BOT_NAME}.",
            f"For more products and services, visit {COMPANY_HTML}.",
        ]
    )
    return "\n".join(lines)


def _deliver_result(bot: TeleBot, sess: Session, path: str, filename: str) -> None:
    caption = _result_caption(sess)
    _delete(bot, sess.chat_id, sess.prompt_message_id)
    with open(path, "rb") as fh:
        bot.send_document(
            sess.chat_id,
            fh,
            visible_file_name=filename,
            caption=caption,
            parse_mode="HTML",
            reply_to_message_id=sess.source_message_id,
            allow_sending_without_reply=True,
            reply_markup=website_keyboard(),
        )


def _compress_session(bot: TeleBot, sess: Session) -> Session | None:
    assert sess.target_bytes is not None
    _edit_prompt(bot, sess, COMPRESSING_TEXT, None)
    dest_dir = _user_dir(sess.user_id)
    try:
        if sess.kind == "pdf":
            dest = dest_dir / f"{_stem(sess.original_name)}_compressed.pdf"
            result = compress_pdf(sess.original_path, dest, sess.target_bytes)
        else:
            dest = dest_dir / f"{_stem(sess.original_name)}_compressed.jpg"
            result = compress_image(sess.original_path, dest, sess.target_bytes)
    except Exception:
        log.exception("compression failed")
        _edit_prompt(
            bot,
            sess,
            "Compression could not be completed. Please send the file again.",
            None,
        )
        sessions.clear(sess.user_id)
        _reset_files(sess.user_id)
        return None

    sess.compressed_path = result.path
    sess.compressed_size = result.size
    sess.under_target = result.under_target

    if sess.kind == "pdf":
        _deliver_result(
            bot,
            sess,
            result.path,
            f"{_stem(sess.original_name)}_compressed.pdf",
        )
        sessions.clear(sess.user_id)
        _reset_files(sess.user_id)
        return None

    sess.state = "await_format"
    sessions.put(sess)
    _edit_prompt(
        bot,
        sess,
        "Compressed. Would you like it returned as an image or as a PDF?",
        format_keyboard(),
    )
    return sess


def _ask_for_file(bot: TeleBot, user_id: int, chat_id: int) -> None:
    previous = sessions.pop_inbox(user_id)
    if previous:
        _delete(bot, previous[0], previous[1])
    sent = bot.send_message(chat_id, COMPRESSOR_TEXT)
    sessions.set_inbox(user_id, chat_id, sent.message_id)


def register_handlers(bot: TeleBot) -> None:
    @bot.message_handler(commands=["start", "help"])
    def start(message: Message) -> None:
        send_home(bot, message.chat.id)
        _delete(bot, message.chat.id, message.message_id)

    @bot.message_handler(commands=["compress"])
    def compress(message: Message) -> None:
        _ask_for_file(bot, message.from_user.id, message.chat.id)
        _delete(bot, message.chat.id, message.message_id)

    @bot.callback_query_handler(func=lambda call: call.data == "home:compressor")
    def on_compressor(call: CallbackQuery) -> None:
        bot.answer_callback_query(call.id)
        chat = call.message.chat if call.message else None
        if chat is None:
            return
        _ask_for_file(bot, call.from_user.id, chat.id)

    @bot.message_handler(commands=["cancel"])
    def cancel(message: Message) -> None:
        sess = sessions.get(message.from_user.id)
        if sess:
            _delete(bot, sess.chat_id, sess.prompt_message_id)
        inbox = sessions.pop_inbox(message.from_user.id)
        if inbox:
            _delete(bot, inbox[0], inbox[1])
        sessions.clear(message.from_user.id)
        _reset_files(message.from_user.id)
        _delete(bot, message.chat.id, message.message_id)

    @bot.message_handler(content_types=["photo"])
    def on_photo(message: Message) -> None:
        photo = message.photo[-1]
        _ingest_file(
            bot,
            message,
            file_id=photo.file_id,
            filename="photo.jpg",
            kind="image",
        )

    @bot.message_handler(content_types=["document"])
    def on_document(message: Message) -> None:
        doc = message.document
        if doc is None:
            return
        name = doc.file_name or "file"
        mime = (doc.mime_type or "").lower()
        suffix = Path(name).suffix.lower()
        if mime == "application/pdf" or suffix == ".pdf":
            kind = "pdf"
            if not name.lower().endswith(".pdf"):
                name = f"{name}.pdf"
        elif mime in IMAGE_MIMES or suffix in IMAGE_SUFFIXES:
            kind = "image"
        else:
            bot.reply_to(message, "Please send a PDF or an image (JPEG, PNG, WebP, or GIF).")
            return
        _ingest_file(bot, message, file_id=doc.file_id, filename=name, kind=kind)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("size:"))
    def on_size(call: CallbackQuery) -> None:
        bot.answer_callback_query(call.id)
        sess = sessions.get(call.from_user.id)
        if sess is None or sess.state not in ("await_size", "await_custom"):
            return
        if call.message:
            sess.prompt_message_id = call.message.message_id

        choice = call.data.split(":", 1)[1]
        if choice == "back":
            sess.state = "await_size"
            sess.custom_unit = None
            sessions.put(sess)
            _edit_prompt(bot, sess, _size_prompt(sess), size_keyboard())
            return
        if choice == "custom_kb":
            sess.state = "await_custom"
            sess.custom_unit = "kb"
            sessions.put(sess)
            _edit_prompt(bot, sess, _custom_prompt("kb"), custom_keyboard())
            return
        if choice == "custom_mb":
            sess.state = "await_custom"
            sess.custom_unit = "mb"
            sessions.put(sess)
            _edit_prompt(bot, sess, _custom_prompt("mb"), custom_keyboard())
            return

        if sess.state != "await_size":
            return
        target = SIZE_BYTES.get(choice)
        if target is None:
            return
        sess.target_bytes = target
        _compress_session(bot, sess)

    @bot.callback_query_handler(func=lambda call: call.data.startswith("fmt:"))
    def on_format(call: CallbackQuery) -> None:
        bot.answer_callback_query(call.id)
        sess = sessions.get(call.from_user.id)
        if sess is None or sess.state != "await_format" or not sess.compressed_path:
            return
        if call.message:
            sess.prompt_message_id = call.message.message_id

        choice = call.data.split(":", 1)[1]
        stem = _stem(sess.original_name)
        if choice == "pdf":
            dest = _user_dir(sess.user_id) / f"{stem}_compressed.pdf"
            try:
                size = _image_to_pdf(sess.compressed_path, dest)
                if sess.target_bytes and size >= sess.target_bytes:
                    tighter = max(1024, sess.target_bytes - 8192)
                    jpeg_path = _user_dir(sess.user_id) / f"{stem}_for_pdf.jpg"
                    compress_image(sess.compressed_path, jpeg_path, tighter)
                    size = _image_to_pdf(str(jpeg_path), dest)
            except Exception:
                log.exception("image to pdf failed")
                _edit_prompt(bot, sess, "The image could not be converted to a PDF. Please try again.", None)
                return
            sess.compressed_size = size
            sess.under_target = not sess.target_bytes or size < sess.target_bytes
            _deliver_result(bot, sess, str(dest), f"{stem}_compressed.pdf")
        else:
            suffix = Path(sess.compressed_path).suffix or ".jpg"
            _deliver_result(bot, sess, sess.compressed_path, f"{stem}_compressed{suffix}")

        sessions.clear(sess.user_id)
        _reset_files(sess.user_id)

    @bot.message_handler(func=lambda m: True, content_types=["text"])
    def on_text(message: Message) -> None:
        if message.text and message.text.startswith("/"):
            return
        sess = sessions.get(message.from_user.id)
        if sess is None or sess.state != "await_custom":
            return

        match = CUSTOM_NUMBER.match(message.text or "")
        if not match:
            _delete(bot, message.chat.id, message.message_id)
            _edit_prompt(
                bot,
                sess,
                f"{_custom_prompt(sess.custom_unit or 'kb')}\n\nPlease send a positive number, for example 250",
                custom_keyboard(),
            )
            return
        value = float(match.group(1))
        if value <= 0:
            _delete(bot, message.chat.id, message.message_id)
            _edit_prompt(
                bot,
                sess,
                f"{_custom_prompt(sess.custom_unit or 'kb')}\n\nPlease send a number greater than 0.",
                custom_keyboard(),
            )
            return

        if sess.custom_unit == "mb":
            target = int(value * 1024 * 1024)
        else:
            target = int(value * 1024)
        _delete(bot, message.chat.id, message.message_id)
        if target < 1024:
            _edit_prompt(
                bot,
                sess,
                f"{_custom_prompt(sess.custom_unit or 'kb')}\n\nThat target is too small. Please choose at least 1 KB.",
                custom_keyboard(),
            )
            return
        sess.target_bytes = target
        _compress_session(bot, sess)


def _ingest_file(bot: TeleBot, message: Message, file_id: str, filename: str, kind: str) -> None:
    user_id = message.from_user.id
    chat_id = message.chat.id

    file_info = bot.get_file(file_id)
    if file_info.file_path is None:
        bot.reply_to(message, "Telegram could not provide a download path. Please send the file as a document.")
        return

    incoming_size = int(file_info.file_size or 0)
    if not quotas.is_unlimited(chat_id, user_id) and quotas.would_exceed(user_id, incoming_size):
        bot.reply_to(
            message,
            LIMIT_MESSAGE,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
        return

    data = bot.download_file(file_info.file_path)
    actual_size = len(data)
    if not quotas.is_unlimited(chat_id, user_id) and quotas.would_exceed(user_id, actual_size):
        bot.reply_to(
            message,
            LIMIT_MESSAGE,
            parse_mode="HTML",
            disable_web_page_preview=True,
        )
        return

    previous = sessions.get(user_id)
    if previous:
        _delete(bot, previous.chat_id, previous.prompt_message_id)
    inbox = sessions.pop_inbox(user_id)
    if inbox:
        _delete(bot, inbox[0], inbox[1])
    sessions.clear(user_id)
    _reset_files(user_id)

    dest = _user_dir(user_id) / filename
    dest.write_bytes(data)

    if not quotas.is_unlimited(chat_id, user_id):
        quotas.record_file(user_id, actual_size)

    sess = Session(
        user_id=user_id,
        chat_id=chat_id,
        original_path=str(dest),
        original_name=filename,
        kind=kind,  # type: ignore[arg-type]
        original_size=len(data),
        state="await_size",
        source_message_id=message.message_id,
        prompt_message_id=0,
    )
    sent = bot.reply_to(
        message,
        _size_prompt(sess),
        reply_markup=size_keyboard(),
    )
    sess.prompt_message_id = sent.message_id
    sessions.put(sess)
