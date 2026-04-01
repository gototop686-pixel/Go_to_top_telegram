from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_language_kb() -> InlineKeyboardMarkup:
    kb = [
        [
            InlineKeyboardButton(text="Русский 🇷🇺", callback_data="lang_ru"),
            InlineKeyboardButton(text="Հայերեն 🇦🇲", callback_data="lang_am")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)
