from datetime import datetime
import pytz
from aiogram import Router, types, Bot, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from config.config import config
from keyboards.reply import get_main_menu_kb, get_language_kb
from keyboards.inline import get_manager_accept_kb
from states.user_states import SalesFunnel
from services.ai_service import ai_service
from database.crud import save_user, log_interaction
from middlewares.i18n import i18n_manager

router = Router()

@router.message(Command("start"))
async def cmd_start(message: Message, i18n, state: FSMContext):
    await state.clear()
    user = message.from_user
    await save_user(user.id, user.username, user.full_name)
    await message.answer(i18n("welcome_msg"), reply_markup=get_language_kb())
    await log_interaction(user.id, 'command', 'start', '/start', 'Welcome message')

@router.message(F.text == "🇷🇺 Русский")
@router.message(F.text == "🇦🇲 Հայերեն")
async def set_language(message: Message, state: FSMContext):
    lang = "ru" if "Русский" in message.text else "am"
    await state.update_data(language=lang)
    
    # Use localized texts
    i18n = lambda key: i18n_manager.get(key, lang)
    
    await message.answer(i18n("lang_selected"), reply_markup=get_main_menu_kb(i18n))

# MANAGER NOTIFICATION HELPERS
async def notify_manager_about_attempt(bot: Bot, user: types.User, context: str = None):
    """Notify the manager regardless of the hour, with context if available."""
    tz = pytz.timezone('Asia/Yerevan')
    now = datetime.now(tz)
    current_hour = now.hour
    
    is_working_hours = config.work_start_hour <= current_hour < config.work_end_hour
    hour_prefix = "⏰ (РАБОЧЕЕ ВРЕМЯ)" if is_working_hours else "🌙 (ВНЕРАБОЧЕЕ ВРЕМЯ)"
    
    msg = f"{hour_prefix} 🙋 Пользователь просит связаться!\n\nИмя: {user.full_name}\nUsername: @{user.username or 'N/A'}\nID: {user.id}\n"
    if context:
        msg += f"\n📝 Контекст диалога (последнее сообщение):\n\"{context}\""
    
    try:
        # We ALWAYS send the notification
        await bot.send_message(
            config.manager_id, 
            msg, 
            reply_markup=get_manager_accept_kb(user.id)
        )
    except Exception as e:
        print(f"Failed to notify manager: {e}")

async def contact_manager(message: Message, i18n, bot: Bot):
    tz = pytz.timezone('Asia/Yerevan')
    now = datetime.now(tz)
    current_hour = now.hour
    
    # Always notify the manager
    await notify_manager_about_attempt(bot, message.from_user, message.text)

    # Check working hours for the USER response
    if config.work_start_hour <= current_hour < config.work_end_hour:
        await message.answer(i18n("wait_for_manager_msg"))
    else:
        # Off-duty
        await message.answer(i18n("off_duty_msg"))
