import json
import re
import logging
import html as html_lib
from aiogram import Router, F, Bot
from aiogram.types import Message
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext

from states.user_states import SupportMode, ManagerChat
from services.ai_service import ai_service
from database.crud import log_interaction
from keyboards.reply import get_main_menu_kb, get_ai_support_kb
from keyboards.inline import get_manager_accept_kb
from middlewares.i18n import i18n_manager
from config.config import config

router = Router()


# ============================================================
# FORM DETECTION & SPLITTING
# ============================================================

# Marker AI can put in response to trigger form
FORM_MARKER = "[SEND_FORM]"


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


def has_form_template(text: str) -> bool:
    """Check if AI response contains a data collection form."""
    indicators = ["Имя:", "Артикул", "Ключевые слова:", "Количество выкупов"]
    count = sum(1 for ind in indicators if ind in text)
    return count >= 3 or FORM_MARKER in text


def split_form_response(text: str):
    """Split AI response into (intro, form_block, outro).
    If no form detected, returns (text, None, None)."""
    text = text.replace(FORM_MARKER, "").strip()

    if not has_form_template(text):
        return text, None, None

    lines = text.split("\n")
    form_start = None
    form_end = None

    # Find form boundaries: lines that look like "Имя:", "Артикул WB:", etc.
    form_field_pattern = re.compile(
        r'^[👤🎯💰🛒🔑📐📦⭐📸🏷️📊📋\s]*'
        r'(Имя|Артикул|Цена товара|Количество выкупов|Ключевые слова|Размеры|Сколько штук|'
        r'Количество отзывов|Доп\.?\s*услуги|Промокод|Անուն|Հոադdelays)'
    )

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        if form_field_pattern.match(stripped):
            if form_start is None:
                form_start = i
            form_end = i

    if form_start is not None and form_end is not None:
        intro = "\n".join(lines[:form_start]).strip()
        form = "\n".join(lines[form_start:form_end + 1]).strip()
        outro = "\n".join(lines[form_end + 1:]).strip()
        # Remove emojis from form for clean copy
        form_clean = re.sub(r'[👤🎯💰🛒🔑📐📦⭐📸🏷️📊📋]\s*', '', form)
        return intro, form_clean, outro

    return text, None, None


# ============================================================
# SAFE SEND HELPERS
# ============================================================

async def send_safe(message: Message, text: str, **kwargs):
    """Send plain text message safely."""
    try:
        await message.answer(text, parse_mode=None, **kwargs)
    except Exception as e:
        logging.error(f"Failed to send message: {e}")
        try:
            safe_text = text[:4000] if len(text) > 4000 else text
            await message.answer(safe_text, parse_mode=None)
        except Exception as e2:
            logging.error(f"Failed to send truncated message: {e2}")
            await message.answer(
                "Произошла ошибка при отправке ответа. Попробуйте ещё раз.",
                parse_mode=None
            )


async def send_with_form(message: Message, text: str, **kwargs):
    """Send AI response. If form detected — send as:
    1. Intro text (plain)
    2. Form (<code> block — one-tap copy in Telegram)
    3. Outro / instruction (plain, with keyboard)
    """
    intro, form_text, outro = split_form_response(text)

    if form_text is None:
        # No form — send as plain text
        await send_safe(message, text, **kwargs)
        return

    # 1. Send intro (plain text, no keyboard)
    if intro:
        await send_safe(message, intro)

    # 2. Send form as HTML <code> block (copyable on tap)
    escaped = html_lib.escape(form_text)
    form_html = f"<code>{escaped}</code>"
    try:
        await message.answer(form_html, parse_mode=ParseMode.HTML)
    except Exception as e:
        logging.warning(f"HTML form failed ({e}), sending plain")
        await send_safe(message, form_text)

    # 3. Send outro or instruction (with keyboard)
    if outro and outro.strip():
        tip = outro.strip() + "\n\nНажмите на блок выше, чтобы скопировать 👆"
        await send_safe(message, tip, **kwargs)
    else:
        await send_safe(
            message,
            "Нажмите на блок выше, чтобы скопировать. Заполните и отправьте одним сообщением 👆",
            **kwargs
        )


# ============================================================
# FILLED FORM DETECTION (client sends back filled data)
# ============================================================

def detect_filled_form(text: str) -> dict | None:
    """Detect if client message is a filled form. Returns parsed fields or None."""
    # Must have at least 3 filled fields with ":"
    lines = text.strip().split("\n")
    fields = {}
    field_map = {
        "имя": "name",
        "артикул": "article",
        "цена": "wb_price",
        "количество выкупов": "buyout_count",
        "выкупов": "buyout_count",
        "ключевые": "keywords",
        "ключевые слова": "keywords",
        "размеры": "dimensions",
        "короб": "box_capacity",
        "сколько штук": "box_capacity",
        "отзыв": "review_count",
        "количество отзывов": "review_count",
        "доп": "extra_services",
        "промокод": "promo_code",
    }

    for line in lines:
        if ":" not in line:
            continue
        key_part, _, val_part = line.partition(":")
        key_clean = re.sub(r'[👤🎯💰🛒🔑📐📦⭐📸🏷️📊📋\s]', '', key_part).strip().lower()
        val_clean = val_part.strip()
        if not val_clean or val_clean == "-":
            continue

        for pattern, field_name in field_map.items():
            if pattern in key_clean:
                fields[field_name] = val_clean
                break

    # Need at least name + article + buyout_count (or 3 any fields)
    if len(fields) >= 3:
        return fields
    return None


# ============================================================
# HANDLERS
# ============================================================

@router.message(F.text.in_([
    i18n_manager.get("btn_ask_question", "ru"),
    i18n_manager.get("btn_ask_question", "am")
]))
async def start_questioning(message: Message, i18n, state: FSMContext):
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

    user_id = message.from_user.id

    # CHECK: Is this a filled form from client?
    filled = detect_filled_form(message.text)
    if filled:
        # Client sent filled form — notify manager immediately
        await send_safe(
            message,
            "Данные получены ✅\n\nПередаю менеджеру. Он подготовит точный расчёт в PDF и свяжется с вами 📋",
            reply_markup=get_ai_support_kb(i18n)
        )
        await log_interaction(user_id, 'ai', 'form_submitted', message.text, "Form received")
        await notify_manager_lead(bot, message.from_user, filled)
        return

    # Regular AI conversation
    answer = await ai_service.get_answer(message.text, language, user_id=user_id)

    # Check for [LEAD_DATA] tag from AI
    clean_answer, lead_data = extract_lead_data(answer)

    await log_interaction(user_id, 'ai', 'questioning', message.text, clean_answer)

    # Send response — with form detection for copyable block
    await send_with_form(message, clean_answer, reply_markup=get_ai_support_kb(i18n))

    # If AI tagged lead data — also notify manager
    if lead_data:
        await notify_manager_lead(bot, message.from_user, lead_data)


async def notify_manager_lead(bot: Bot, user, lead_data: dict):
    """Notify manager about a new lead — triggers manager to join chat."""
    msg = (
        f"🆕 НОВАЯ ЗАЯВКА\n\n"
        f"👤 Клиент: {user.full_name}\n"
        f"📱 Telegram: @{user.username or 'нет username'}\n"
        f"🆔 ID: {user.id}\n\n"
        f"Данные клиента:\n"
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

    msg += "\nПодготовьте PDF-расчёт для оплаты и подключитесь к чату."

    try:
        await bot.send_message(
            config.manager_id,
            msg,
            reply_markup=get_manager_accept_kb(user.id)
        )
    except Exception as e:
        logging.error(f"Failed to notify manager: {e}")
