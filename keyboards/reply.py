from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from typing import Callable

def get_language_kb() -> ReplyKeyboardMarkup:
    kb = [
        [KeyboardButton(text="\U0001f1f7\U0001f1fa \u0420\u0443\u0441\u0441\u043a\u0438\u0439"), KeyboardButton(text="\U0001f1e6\U0001f1f2 \u0540\u0561\u0575\u0565\u0580\u0565\u0576")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def get_main_menu_kb(i18n: Callable) -> ReplyKeyboardMarkup:
    """New 6-button main menu (2 columns x 3 rows)."""
    kb = [
        [KeyboardButton(text=i18n("btn_contact_manager")), KeyboardButton(text=i18n("btn_faq"))],
        [KeyboardButton(text=i18n("btn_price_list")),      KeyboardButton(text=i18n("btn_how_to_order"))],
        [KeyboardButton(text=i18n("btn_about_us")),         KeyboardButton(text=i18n("btn_change_language"))],
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def get_existing_client_kb(i18n: Callable) -> ReplyKeyboardMarkup:
    kb = [
        [KeyboardButton(text=i18n("btn_check_status"))],
        [KeyboardButton(text=i18n("btn_contact_manager")), KeyboardButton(text=i18n("btn_ask_question"))],
        [KeyboardButton(text=i18n("btn_back_to_menu"))]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def get_ai_support_kb(i18n: Callable) -> ReplyKeyboardMarkup:
    kb = [
        [KeyboardButton(text=i18n("btn_contact_manager"))],
        [KeyboardButton(text=i18n("btn_back_to_menu"))]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def get_back_kb(i18n: Callable) -> ReplyKeyboardMarkup:
    kb = [[KeyboardButton(text=i18n("btn_back_to_menu"))]]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def get_faq_kb(i18n: Callable) -> ReplyKeyboardMarkup:
    """FAQ sub-menu keyboard — used for Armenian FAQ list."""
    from handlers.faq_data import ARMENIAN_FAQ
    kb = []
    # "Contact manager" button at the top
    kb.append([KeyboardButton(text=i18n("btn_contact_manager"))])
    # FAQ questions as buttons (each on its own row)
    for item in ARMENIAN_FAQ:
        kb.append([KeyboardButton(text=item["question"])])
    # Back to menu
    kb.append([KeyboardButton(text=i18n("btn_back_to_menu"))])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def get_price_categories_kb(i18n: Callable) -> ReplyKeyboardMarkup:
    """Pricing sub-menu: 5 categories + back button."""
    kb = [
        [KeyboardButton(text=i18n("btn_price_main"))],
        [KeyboardButton(text=i18n("btn_price_reviews"))],
        [KeyboardButton(text=i18n("btn_price_photo_video"))],
        [KeyboardButton(text=i18n("btn_price_fulfillment"))],
        [KeyboardButton(text=i18n("btn_price_delivery"))],
        [KeyboardButton(text=i18n("btn_back_to_menu"))],
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
