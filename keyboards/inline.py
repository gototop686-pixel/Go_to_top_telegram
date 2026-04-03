from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_language_kb() -> InlineKeyboardMarkup:
    kb = [
        [
            InlineKeyboardButton(text="Русский 🇷🇺", callback_data="lang_ru"),
            InlineKeyboardButton(text="Հայերեն 🇦🇲", callback_data="lang_am")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)
def get_manager_accept_kb(user_id: int) -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton(text="✅ Принять чат", callback_data=f"accept_chat:{user_id}")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)
