import json
import re
import logging
from aiogram import Router, F, Bot
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from states.user_states import SupportMode, ManagerChat
from services.ai_service import ai_service
from database.crud import log_interaction
from keyboards.reply import get_main_menu_kb, get_ai_support_kb
from keyboards.inline import get_manager_accept_kb
from middlewares.i18n import i18n_manager
from handlers.common import notify_manager_about_attempt
from config.config import config

router = Router()

ORDER_KEYWORDS = [
    "артикул", "articul", "заказ", "order", "պատվdelays", 
    "хочу купить", "хочу заказать", "հաշվարկ", "расчет", "расчёт"
]


def extract_lead_data(response: str):
    """Extract lead data from AI response if tagged."""
    match = re.search(r'\[LEAD_DATA\](.*?)\[/LEAD_DATA\]', response, re.DOTALL)
    if match:
        clean_response = response[:match.start()].strip()
        try:
            lead_data = json.loads(match.group(1))
        except (json.JSONDecodeError, Exception):
            lead_data = None
        return clean_response, lead_data
    return response, None


async def send_safe(message: Message, text: str, **kwargs):
    """Send message safely, falling back to plain text if formatting fails."""
    try:
        await message.answer(text, parse_mode=None, **kwargs)
    except Exception as e:
        logging.error(f"Failed to send message: {e}")
        try:
            # Truncate if too long
            safe_text = text[:4000] if len(text) > 4000 else text
            await message.answer(safe_text, parse_mode=None)
        except Exception as e2:
            logging.error(f"Failed to send even truncated message: {e2}")
            await message.answer(
                "Произошла ошибка при отправке ответа. Попробуйте задать вопрос ещё раз.", 
                parse_mode=None
            )


@router.message(F.text.in_([
    i18n_manager.get("btn_ask_question", "ru"), 
    i18n_manager.get("btn_ask_question", "am")
]))
async def start_questioning(message: Message, i18n, state: FSMContext):
    # Don't enter AI mode if in manager chat
    current_state = await state.get_state()
    if current_state == ManagerChat.in_chat.state:
        return
    
    await state.set_state(SupportMode.asking_question)
    await send_safe(message, i18n("ask_question_prompt"), reply_markup=get_ai_support_kb(i18n))


@router.message(SupportMode.asking_question)
async def process_question(message: Message, i18n, language: str, state: FSMContext, bot: Bot):
    # Back to menu
    if message.text in [
        i18n_manager.get("btn_back_to_menu", "ru"), 
        i18n_manager.get("btn_back_to_menu", "am")
    ]:
        await state.clear()
        await send_safe(message, i18n("main_menu"), reply_markup=get_main_menu_kb(i18n))
        return
    
    # Calculate on site
    if message.text in [
        i18n_manager.get("btn_calc_on_site", "ru"), 
        i18n_manager.get("btn_calc_on_site", "am")
    ]:
        await send_safe(message, i18n("calc_on_site_msg"), reply_markup=get_ai_support_kb(i18n))
        return

    # Contact manager
    if message.text in [
        i18n_manager.get("btn_contact_manager", "ru"), 
        i18n_manager.get("btn_contact_manager", "am")
    ]:
        from handlers.common import contact_manager
        await contact_manager(message, i18n, bot)
        return

    # Get AI answer with conversation history
    user_id = message.from_user.id
    answer = await ai_service.get_answer(message.text, language, user_id=user_id)
    
    # Check for lead data
    clean_answer, lead_data = extract_lead_data(answer)
    
    # Log interaction
    await log_interaction(user_id, 'ai', 'questioning', message.text, clean_answer)

    # Send response (plain text, no parse_mode)
    await send_safe(message, clean_answer, reply_markup=get_ai_support_kb(i18n))
    
    # If lead data detected (client sent filled form) — notify manager
    if lead_data:
        await notify_manager_lead(bot, message.from_user, lead_data)


async def notify_manager_lead(bot: Bot, user, lead_data: dict):
    """Notify manager about a complete lead collected by AI."""
    msg = (
        f"🆕 ЗАЯВКА ОТ ЛИИ (AI собрал данные)\n\n"
        f"👤 Клиент: {user.full_name}\n"
        f"📱 Telegram: @{user.username or 'N/A'}\n"
        f"🆔 ID: {user.id}\n\n"
    )
    
    field_labels = {
        "name": "👤 Имя",
        "article": "🎯 Артикул",
        "wb_price": "💰 Цена WB",
        "buyout_count": "🛒 Выкупов",
        "keywords": "🔑 Ключи",
        "review_count": "⭐ Отзывов",
        "dimensions": "📐 Размеры",
        "box_capacity": "📦 Короб",
        "extra_services": "📸 Доп. услуги",
        "promo_code": "🏷️ Промокод",
    }
    
    for key, label in field_labels.items():
        value = lead_data.get(key)
        if value:
            msg += f"{label}: {value}\n"
    
    try:
        await bot.send_message(
            config.manager_id, 
            msg, 
            reply_markup=get_manager_accept_kb(user.id)
        )
    except Exception as e:
        logging.error(f"Failed to notify manager about lead: {e}")
