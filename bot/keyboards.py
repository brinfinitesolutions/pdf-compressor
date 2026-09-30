from telebot.types import InlineKeyboardButton, InlineKeyboardMarkup

SITE_URL = "https://www.brinfinitesolutions.com"

SIZE_BYTES = {
    "200kb": 200 * 1024,
    "300kb": 300 * 1024,
    "500kb": 500 * 1024,
    "1mb": 1024 * 1024,
}


def home_keyboard() -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("Proceed Compressor", callback_data="home:compressor"))
    markup.row(InlineKeyboardButton("Website", url=SITE_URL))
    return markup


def website_keyboard() -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup()
    markup.row(InlineKeyboardButton("Website", url=SITE_URL))
    return markup


def size_keyboard() -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("200 KB", callback_data="size:200kb"),
        InlineKeyboardButton("300 KB", callback_data="size:300kb"),
        InlineKeyboardButton("500 KB", callback_data="size:500kb"),
        InlineKeyboardButton("1 MB", callback_data="size:1mb"),
        InlineKeyboardButton("Custom KB", callback_data="size:custom_kb"),
        InlineKeyboardButton("Custom MB", callback_data="size:custom_mb"),
    )
    return markup


def custom_keyboard() -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup(row_width=1)
    markup.add(InlineKeyboardButton("Back", callback_data="size:back"))
    return markup


def format_keyboard() -> InlineKeyboardMarkup:
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("Send as image", callback_data="fmt:image"),
        InlineKeyboardButton("Send as PDF", callback_data="fmt:pdf"),
    )
    return markup
