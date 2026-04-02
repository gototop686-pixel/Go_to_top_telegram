from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from typing import Callable

def get_language_kb() -> ReplyKeyboardMarkup:
    kb = [
        [KeyboardButton(text="🇷🇺 Русский"), KeyboardButton(text="🇦🇲 Հայերեն")]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_main_menu_kb(i18n: Callable) -> ReplyKeyboardMarkup:
    kb = [
        [KeyboardButton(text=i18n("btn_new_client"))],
        [KeyboardButton(text=i18n("btn_existing_client")), KeyboardButton(text=i18n("btn_ask_question"))]
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
        [KeyboardButton(text=i18n("btn_calc_on_site"))],
        [KeyboardButton(text=i18n("btn_contact_manager"))],
        [KeyboardButton(text=i18n("btn_back_to_menu"))]
    ]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_back_kb(i18n: Callable) -> ReplyKeyboardMarkup:
    kb = [[KeyboardButton(text=i18n("btn_back_to_menu"))]]
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)
