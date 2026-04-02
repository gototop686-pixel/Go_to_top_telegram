from aiogram import Router, F, Bot
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from database.crud import update_user_language, get_user
from keyboards.inline import get_language_kb
from keyboards.reply import get_main_menu_kb, get_existing_client_kb
from config.config import config

from middlewares.i18n import i18n_manager

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message, i18n, state: FSMContext, bot: Bot):
    await state.clear()
    
    # Notify manager about new user
    user = message.from_user
    msg = f"👤 Новый пользователь зашел в бота!\n\nИмя: {user.full_name}\nUsername: @{user.username or 'N/A'}\nID: {user.id}"
    try:
        await bot.send_message(config.manager_id, msg)
    except Exception as e:
        print(f"Failed to notify manager on start: {e}")

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

@router.message(F.text.in_([i18n_manager.get("btn_existing_client", "ru"), i18n_manager.get("btn_existing_client", "am")]))
async def existing_client_menu(message: Message, i18n):
    await message.answer(i18n("existing_client_menu"), reply_markup=get_existing_client_kb(i18n))

@router.message(F.text.in_([i18n_manager.get("btn_check_status", "ru"), i18n_manager.get("btn_check_status", "am")]))
async def check_status(message: Message, i18n):
    await message.answer(i18n("status_stub"))

from datetime import datetime, timedelta, timezone
from keyboards.inline import get_language_kb, get_manager_accept_kb

# ... (other imports) ...

@router.message(F.text.in_([i18n_manager.get("btn_contact_manager", "ru"), i18n_manager.get("btn_contact_manager", "am")]))
async def contact_manager(message: Message, i18n, bot: Bot):
    # Erevan Time (UTC+4)
    now_erevan = datetime.now(timezone.utc) + timedelta(hours=4)
    current_hour = now_erevan.hour
    
    # Check working hours
    if config.work_start_hour <= current_hour < config.work_end_hour:
        # Notify user (Wait message)
        wait_msg = i18n("wait_for_manager_msg")
        await message.answer(wait_msg)
        
        # Notify manager about contact request with ACTION button
        user = message.from_user
        msg = f"🙋 Пользователь просит связаться!\n\nИмя: {user.full_name}\nUsername: @{user.username or 'N/A'}\nID: {user.id}"
        try:
            await bot.send_message(
                config.manager_id, 
                msg, 
                reply_markup=get_manager_accept_kb(user.id)
            )
        except Exception as e:
            print(f"Failed to notify manager: {e}")
            
    else:
        # Off-duty
        await message.answer(i18n("off_duty_msg"))
