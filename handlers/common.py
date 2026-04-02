from datetime import datetime
import logging
import pytz
from aiogram import Router, types, Bot, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from config.config import config
from keyboards.reply import get_main_menu_kb, get_language_kb
from keyboards.inline import get_manager_accept_kb
from services.ai_service import ai_service
from database.crud import save_user, update_user_language, log_interaction
from middlewares.i18n import i18n_manager

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message, i18n, state: FSMContext):
    await state.clear()
    user = message.from_user
    await save_user(user.id, user.username, user.full_name)
    
    # Clear AI conversation history on /start
    ai_service.clear_history(user.id)
    
    await message.answer(i18n("welcome_msg"), reply_markup=get_language_kb(), parse_mode=None)
    
    # Notify manager
    manager_msg = (
        f"🆕 Пользователь зашел в бота!\n\n"
        f"Имя: {user.full_name}\n"
        f"Username: @{user.username or 'N/A'}\n"
        f"ID: {user.id}"
    )
    try:
        await message.bot.send_message(config.manager_id, manager_msg, parse_mode=None)
    except Exception as e:
        logging.error(f"Failed to notify manager: {e}")
        
    await log_interaction(user.id, 'command', 'start', '/start', 'Welcome message')


@router.message(F.text == "🇷🇺 Русский")
@router.message(F.text == "🇦🇲 Հայերեն")
async def set_language(message: Message, state: FSMContext):
    lang = "ru" if "Русский" in message.text else "am"
    await state.update_data(language=lang)
    
    # Persist to database
    await update_user_language(message.from_user.id, lang)
    
    i18n = lambda key: i18n_manager.get(key, lang)
    
    await message.answer(i18n("lang_selected"), reply_markup=get_main_menu_kb(i18n), parse_mode=None)


# MANAGER NOTIFICATION HELPERS
async def notify_manager_about_attempt(bot: Bot, user: types.User, context: str = None):
    """Notify the manager with context."""
    tz = pytz.timezone('Asia/Yerevan')
    now = datetime.now(tz)
    current_hour = now.hour
    
    is_working = config.work_start_hour <= current_hour < config.work_end_hour
    prefix = "⏰ (РАБОЧЕЕ ВРЕМЯ)" if is_working else "🌙 (ВНЕРАБОЧЕЕ ВРЕМЯ)"
    
    msg = (
        f"{prefix} 🙋 Клиент просит связаться!\n\n"
        f"Имя: {user.full_name}\n"
        f"Username: @{user.username or 'N/A'}\n"
        f"ID: {user.id}\n"
    )
    if context:
        msg += f"\n📝 Контекст:\n{context}"
    
    try:
        await bot.send_message(
            config.manager_id, 
            msg, 
            reply_markup=get_manager_accept_kb(user.id),
            parse_mode=None
        )
    except Exception as e:
        logging.error(f"Failed to notify manager: {e}")


async def contact_manager(message: Message, i18n, bot: Bot):
    tz = pytz.timezone('Asia/Yerevan')
    now = datetime.now(tz)
    current_hour = now.hour
    
    await notify_manager_about_attempt(bot, message.from_user, message.text)

    if config.work_start_hour <= current_hour < config.work_end_hour:
        await message.answer(i18n("wait_for_manager_msg"), parse_mode=None)
    else:
        await message.answer(i18n("off_duty_msg"), parse_mode=None)
