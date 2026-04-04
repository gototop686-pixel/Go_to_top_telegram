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


def get_waiting_for_manager_kb(i18n: Callable) -> ReplyKeyboardMarkup:
    """Keyboard shown while waiting for manager — cancel + menu."""
    kb = [
        [KeyboardButton(text=i18n("btn_cancel_request"))],
        [KeyboardButton(text=i18n("btn_back_to_menu"))],
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)


def get_faq_kb(i18n: Callable) -> ReplyKeyboardMarkup:
    """FAQ sub-menu keyboard — Armenian FAQ list with category headers.
    Back-to-menu and contact-manager are at the TOP so users don't have
    to scroll past 29 questions to reach them."""
    from handlers.faq_data import ARMENIAN_FAQ_CATEGORIES
    kb = []
    # Navigation buttons at the TOP — easy access without scrolling
    kb.append([
        KeyboardButton(text=i18n("btn_back_to_menu")),
        KeyboardButton(text=i18n("btn_contact_manager")),
    ])
    # FAQ questions grouped by category
    for cat in ARMENIAN_FAQ_CATEGORIES:
        # Category header as a non-clickable-looking button (just a label)
        kb.append([KeyboardButton(text=cat["title"])])
        # Questions under this category
        for item in cat["questions"]:
            kb.append([KeyboardButton(text=item["question"])])
    # Back to menu at the bottom too (convenience)
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
