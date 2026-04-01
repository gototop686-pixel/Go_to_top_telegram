from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from database.crud import update_user_language, get_user
from keyboards.inline import get_language_kb
from keyboards.reply import get_main_menu_kb, get_existing_client_kb

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message, i18n, state: FSMContext):
    await state.clear()
    await message.answer(i18n("greeting"), reply_markup=get_language_kb())

@router.callback_query(F.data.startswith("lang_"))
async def set_language(callback: CallbackQuery, i18n_manager, i18n, state: FSMContext):
    lang = callback.data.split("_")[1]
    await update_user_language(callback.from_user.id, lang)
    
    # Get translated main menu with the new language
    text = i18n_manager.get("main_menu", lang)
    kb = get_main_menu_kb(lambda key: i18n_manager.get(key, lang))
    
    await callback.message.delete()
    await callback.message.answer(text, reply_markup=kb)
    await callback.answer()

@router.message(F.text.contains("🔙"))
@router.message(F.text.casefold().in_({"back", "назад", "меню", "menu"}))
async def go_to_main_menu(message: Message, i18n, state: FSMContext):
    await state.clear()
    await message.answer(i18n("main_menu"), reply_markup=get_main_menu_kb(i18n))

@router.message(lambda m, i18n: m.text == i18n("btn_existing_client"))
async def existing_client_menu(message: Message, i18n):
    await message.answer(i18n("existing_client_menu"), reply_markup=get_existing_client_kb(i18n))

@router.message(lambda m, i18n: m.text == i18n("btn_check_status"))
async def check_status(message: Message, i18n):
    await message.answer(i18n("status_stub"))

@router.message(lambda m, i18n: m.text == i18n("btn_contact_manager"))
async def contact_manager(message: Message, i18n):
    # In a real app, this might notify the manager
    await message.answer(i18n("contact_manager_msg"))
