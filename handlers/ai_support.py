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
# HARDCODED FORM — bot sends this, NOT the AI
# ============================================================

FORM_TEMPLATE = (
    "Имя:\n"
    "Артикул WB:\n"
    "Цена товара на WB (которую видит покупатель):\n"
    "Количество выкупов (мин. 20):\n"
    "Ключевые слова:\n"
    "Размеры товара с упаковкой (ДxШxВ):\n"
    "Сколько штук помещается в короб 60x40x40:\n"
    "Количество отзывов (если нужны):\n"
    "Доп. услуги (фото, видео, переупаковка):\n"
    "Промокод (если есть):"
)

FORM_INTRO = "📋 Для расчёта заполните форму ниже.\nНажмите на блок — он скопируется. Заполните и отправьте одним сообщением:"

FORM_OUTRO = "☝️ Нажмите на текст выше — он скопируется.\nЗаполните напротив каждого пункта и отправьте мне одним сообщением."


# ============================================================
# FORM DETECTION
# ============================================================

# Words that indicate AI wants to send the form
FORM_TRIGGER_WORDS = [
    "скопируйте", "заполните форму", "заполните эту форму",
    "заполните, пожалуйста", "форму для заполнения",
    "нужно от вас", "нужна следующая информация",
    "мне нужны от вас", "отправьте одним сообщением",
    "данные для расчёта", "мне нужны ваши данные",
    "заполните форму ниже",
    "[SEND_FORM]",
]

# Form field indicators in AI response
FORM_FIELD_WORDS = ["Имя:", "Артикул", "Ключевые слова:", "Количество выкупов"]


# ============================================================
# MANAGER REQUEST DETECTION (client wants live manager)
# ============================================================

MANAGER_TRIGGER_PHRASES = [
    # Russian — direct requests
    "хочу с менеджером", "дайте менеджера", "позовите менеджера",
    "мне нужен менеджер", "свяжите с менеджером", "переключите на менеджера",
    "хочу общаться с менеджером", "хочу поговорить с менеджером",
    "соедините с менеджером", "можно менеджера", "где менеджер",
    "нужен менеджер", "вызовите менеджера", "подключите менеджера",
    "перевести на менеджера", "переведите на менеджера",
    "хочу с человеком", "дайте человека", "хочу поговорить с человеком",
    "мне нужен человек", "свяжите с человеком", "переключите на человека",
    "хочу общаться с человеком", "соедините с человеком",
    # Russian — indirect / colloquial
    "живой чат", "живой оператор", "живой человек",
    "хочу живого", "дайте живого",
    "не хочу с ботом", "не хочу с роботом",
    "хватит бота", "надоел бот", "бот не помогает",
    "хочу с оператором", "дайте оператора", "нужен оператор",
    "можно с оператором", "переключите на оператора",
    "хочу с консультантом", "нужен консультант",
    "хочу связаться с менеджером", "как связаться с менеджером",
    "менеджер нужен", "оператор нужен",
    "позвать менеджера", "позвать человека",
    # Armenian (transliterated / mixed)
    "մenedjer", "менеджер петк э",
    "менеджери хет", "менеджерин асек",
]

# Compiled patterns for more flexible matching
MANAGER_TRIGGER_PATTERNS = [
    r"менеджер\w*",           # менеджер, менеджера, менеджером, менеджеру
    r"оператор\w*",           # оператор, оператора
    r"консультант\w*",        # консультант, консультанта
    r"живо[йего]\s+(?:чат|оператор|человек|менеджер)",
    r"(?:хочу|нужен|дайте|можно|позовите|переключите|свяжите|соедините|подключите)\s+.*?(?:менеджер|человек|оператор|консультант)",
    r"(?:не\s+хочу|хватит|надоел)\s+.*?(?:бот|робот)",
    r"(?:поговорить|общаться|связаться|пообщаться)\s+.*?(?:менеджер|человек|оператор|консультант)",
]


def wants_manager(text: str) -> bool:
    """Check if client wants to talk to a live manager."""
    text_lower = text.lower().strip()

    # Direct phrase match
    for phrase in MANAGER_TRIGGER_PHRASES:
        if phrase in text_lower:
            return True

    # Regex pattern match (more flexible word order / forms)
    for pattern in MANAGER_TRIGGER_PATTERNS:
        if re.search(pattern, text_lower):
            return True

    return False


def ai_wants_form(text: str) -> bool:
    """Check if AI response is trying to send a data collection form."""
    text_lower = text.lower()
    # Check trigger phrases
    for trigger in FORM_TRIGGER_WORDS:
        if trigger.lower() in text_lower:
            return True
    # Check if response contains 3+ form field names
    count = sum(1 for w in FORM_FIELD_WORDS if w in text)
    return count >= 3


def strip_form_from_ai(text: str) -> str:
    """Remove form-like content from AI response, keep only the intro part."""
    text = text.replace("[SEND_FORM]", "").strip()
    lines = text.split("\n")
    clean_lines = []
    in_form = False
    for line in lines:
        stripped = line.strip()
        # Detect start of form fields
        if re.match(r'^[👤🎯💰🛒🔑📐📦⭐📸🏷️📊📋\s]*(?:Имя|Артикул|Цена товара|Количество выкупов|Ключевые слова|Размеры|Сколько штук|Количество отзывов|Доп\.|Промокод)', stripped):
            in_form = True
            continue
        if in_form and (not stripped or re.match(r'^[👤🎯💰🛒🔑📐📦⭐📸🏷️📊📋\-\s]', stripped)):
            continue
        if in_form and stripped:
            in_form = False
        # Skip "скопируйте" / "нажмите" instructions (AI's version)
        if any(w in stripped.lower() for w in ["скопируйте", "нажмите на блок", "отправьте одним сообщением"]):
            continue
        clean_lines.append(line)
    result = "\n".join(clean_lines).strip()
    # If nothing left, return a generic intro
    if not result or len(result) < 10:
        return FORM_INTRO
    return result


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


# ============================================================
# FILLED FORM DETECTION (client sends back data)
# ============================================================

FIELD_PATTERNS = {
    "name":          [r"имя", r"name"],
    "article":       [r"артикул", r"article"],
    "wb_price":      [r"цена", r"price", r"стоимость"],
    "buyout_count":  [r"выкуп", r"количество выкупов", r"buyout"],
    "keywords":      [r"ключев", r"keyword", r"запрос"],
    "dimensions":    [r"размер", r"дxшxв", r"dimension"],
    "box_capacity":  [r"короб", r"штук.*короб", r"box"],
    "review_count":  [r"отзыв", r"review"],
    "extra_services":[r"доп", r"услуг", r"фото", r"видео"],
    "promo_code":    [r"промо", r"promo", r"скидк"],
}


def detect_filled_form(text: str) -> dict | None:
    """Detect if client sent a filled form. Returns parsed fields or None."""
    fields, _ = _parse_form_fields(text)
    # Need at least 3 filled fields to count as a complete form
    if len(fields) >= 3:
        return fields
    return None


def _parse_form_fields(text: str) -> tuple[dict, int]:
    """Parse form fields from text. Returns (filled_fields, total_form_lines).
    total_form_lines > 0 means the text looks like a form attempt."""
    lines = text.strip().split("\n")
    fields = {}
    form_line_count = 0

    for line in lines:
        if ":" not in line:
            continue
        key_part, _, val_part = line.partition(":")
        key_clean = re.sub(r'[^\w\s]', '', key_part, flags=re.UNICODE).strip().lower()
        val_clean = val_part.strip()

        # Check if this line matches any known form field
        matched_field = None
        for field_name, patterns in FIELD_PATTERNS.items():
            for pat in patterns:
                if re.search(pat, key_clean):
                    matched_field = field_name
                    break
            if matched_field:
                break

        if matched_field:
            form_line_count += 1
            if val_clean and val_clean not in ["-", "—", "нет", "не нужны"]:
                if matched_field not in fields:
                    fields[matched_field] = val_clean

    return fields, form_line_count


def detect_incomplete_form(text: str) -> tuple[dict, list] | None:
    """Detect if client tried to send a form but didn't fill enough fields.
    Returns (filled_fields, missing_field_names) or None if not a form at all."""
    fields, form_lines = _parse_form_fields(text)

    # If text has 3+ form-like lines, it's a form attempt
    if form_lines < 3:
        return None

    # It IS a form attempt. Check what's missing.
    required_fields = ["name", "article", "buyout_count"]
    important_fields = ["name", "article", "wb_price", "buyout_count", "keywords"]

    field_labels_ru = {
        "name": "Имя",
        "article": "Артикул WB",
        "wb_price": "Цена товара на WB",
        "buyout_count": "Количество выкупов",
        "keywords": "Ключевые слова",
    }

    missing = []
    for f in important_fields:
        if f not in fields:
            missing.append(field_labels_ru.get(f, f))

    if len(fields) >= 3:
        # Enough data — this is a valid form (handled by detect_filled_form)
        return None

    return fields, missing


# ============================================================
# SEND HELPERS
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
            logging.error(f"Failed to send truncated: {e2}")
            await message.answer("Произошла ошибка. Попробуйте ещё раз.", parse_mode=None)


async def send_copyable_form(message: Message, **kwargs):
    """Send the data collection form as ONE message:
    Intro + <pre> block (green bg + left border + copy button in Telegram) + outro.
    All in a single message so the client sees one clean bubble.
    """
    escaped = html_lib.escape(FORM_TEMPLATE)
    # <pre> in Telegram renders as: green background, thick left border,
    # and a "Copy" button in the top-right corner — exactly like crypto address blocks.
    combined_html = (
        f"{html_lib.escape(FORM_INTRO)}\n\n"
        f"<pre>{escaped}</pre>\n\n"
        f"{html_lib.escape(FORM_OUTRO)}"
    )
    try:
        await message.answer(combined_html, parse_mode=ParseMode.HTML, **kwargs)
    except Exception as e:
        logging.warning(f"HTML <pre> form failed: {e}")
        # Fallback: send as plain text in one message
        fallback = f"{FORM_INTRO}\n\n{FORM_TEMPLATE}\n\n{FORM_OUTRO}"
        await send_safe(message, fallback, **kwargs)


async def send_ai_response(message: Message, text: str, **kwargs):
    """Send AI response. If AI tried to include a form — replace with
    our hardcoded copyable form. Otherwise send as plain text."""
    if ai_wants_form(text):
        # AI wanted to send form — strip AI's form, send as ONE message with <pre> block
        intro = strip_form_from_ai(text)
        custom_intro = intro if (intro and intro != FORM_INTRO) else None
        escaped_form = html_lib.escape(FORM_TEMPLATE)

        if custom_intro:
            # AI had a custom intro — use it instead of default
            combined_html = (
                f"{html_lib.escape(custom_intro)}\n\n"
                f"<pre>{escaped_form}</pre>\n\n"
                f"{html_lib.escape(FORM_OUTRO)}"
            )
        else:
            combined_html = (
                f"{html_lib.escape(FORM_INTRO)}\n\n"
                f"<pre>{escaped_form}</pre>\n\n"
                f"{html_lib.escape(FORM_OUTRO)}"
            )

        try:
            await message.answer(combined_html, parse_mode=ParseMode.HTML, **kwargs)
        except Exception as e:
            logging.warning(f"HTML <pre> form in AI response failed: {e}")
            fallback = f"{custom_intro or FORM_INTRO}\n\n{FORM_TEMPLATE}\n\n{FORM_OUTRO}"
            await send_safe(message, fallback, **kwargs)
    else:
        await send_safe(message, text, **kwargs)


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
    if not message.text:
        return

    # Back to menu
    if message.text in [
        i18n_manager.get("btn_back_to_menu", "ru"),
        i18n_manager.get("btn_back_to_menu", "am")
    ]:
        await state.clear()
        await send_safe(message, i18n("main_menu"), reply_markup=get_main_menu_kb(i18n))
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

    # CHECK 0: Does client want to talk to a manager? (text triggers)
    if wants_manager(message.text):
        logging.info(f"Manager request detected from user {user_id}: {message.text[:80]}")
        await send_safe(
            message,
            "Передаю ваш запрос менеджеру 👋\nОн свяжется с вами в ближайшее время!",
            reply_markup=get_ai_support_kb(i18n)
        )
        await notify_manager_contact_request(bot, message.from_user, message.text)
        await log_interaction(user_id, 'ai', 'manager_request', message.text, "Manager request forwarded")
        return

    # CHECK 1: Is this a FULLY filled form from client? (3+ filled fields)
    filled = detect_filled_form(message.text)
    if filled:
        logging.info(f"Filled form detected from user {user_id}: {filled}")
        await send_safe(
            message,
            "Данные получены ✅\n\nПередаю менеджеру для подготовки расчёта. Менеджер свяжется с вами в ближайшее время 📋",
            reply_markup=get_ai_support_kb(i18n)
        )
        await log_interaction(user_id, 'ai', 'form_submitted', message.text, "Form received")
        await notify_manager_lead(bot, message.from_user, filled, message.text)
        return

    # CHECK 2: Is this an INCOMPLETE form attempt? (looks like form but <3 filled fields)
    incomplete = detect_incomplete_form(message.text)
    if incomplete:
        partial_fields, missing_names = incomplete
        logging.info(f"Incomplete form from user {user_id}: filled={partial_fields}, missing={missing_names}")

        # Tell client what's missing and resend the form
        missing_text = ", ".join(missing_names)
        await send_safe(
            message,
            f"Спасибо за данные, но не все поля заполнены ⚠️\n\n"
            f"Не хватает: {missing_text}\n\n"
            f"Пожалуйста, скопируйте форму ещё раз, заполните ВСЕ поля и отправьте одним сообщением 👇"
        )
        await send_copyable_form(message, reply_markup=get_ai_support_kb(i18n))

        # ALWAYS notify manager about the attempt
        await notify_manager_incomplete_form(bot, message.from_user, partial_fields, missing_names, message.text)
        await log_interaction(user_id, 'ai', 'form_incomplete', message.text, f"Missing: {missing_text}")
        return

    # Regular AI conversation
    answer = await ai_service.get_answer(message.text, language, user_id=user_id)

    # Check for [LEAD_DATA] tag from AI
    clean_answer, lead_data = extract_lead_data(answer)

    await log_interaction(user_id, 'ai', 'questioning', message.text, clean_answer)

    # Send response — intercept form if AI tried to include one
    await send_ai_response(message, clean_answer, reply_markup=get_ai_support_kb(i18n))

    # If AI tagged lead data — also notify manager
    if lead_data:
        await notify_manager_lead(bot, message.from_user, lead_data, message.text)


async def notify_manager_contact_request(bot: Bot, user, raw_text: str = ""):
    """Notify manager that client explicitly asked for a live manager."""
    msg = (
        f"🙋 КЛИЕНТ ПРОСИТ МЕНЕДЖЕРА\n\n"
        f"👤 Клиент: {user.full_name}\n"
        f"📱 Telegram: @{user.username or 'нет username'}\n"
        f"🆔 ID: {user.id}\n\n"
    )

    if raw_text:
        msg += f"💬 Сообщение: {raw_text[:500]}\n\n"

    msg += "Клиент хочет общаться с менеджером напрямую."

    try:
        await bot.send_message(
            config.manager_id,
            msg,
            reply_markup=get_manager_accept_kb(user.id)
        )
        logging.info(f"Manager notified about contact request from user {user.id}")
    except Exception as e:
        logging.error(f"Failed to notify manager about contact request: {e}")


async def notify_manager_incomplete_form(bot: Bot, user, partial_fields: dict, missing: list, raw_text: str = ""):
    """Notify manager that a client tried to send a form but it's incomplete."""
    msg = (
        f"⚠️ НЕПОЛНАЯ ЗАЯВКА\n\n"
        f"👤 Клиент: {user.full_name}\n"
        f"📱 Telegram: @{user.username or 'нет username'}\n"
        f"🆔 ID: {user.id}\n\n"
    )

    if partial_fields:
        msg += "Заполнено:\n"
        field_labels = {
            "name": "👤 Имя", "article": "🎯 Артикул", "wb_price": "💰 Цена WB",
            "buyout_count": "🛒 Выкупов", "keywords": "🔑 Ключи",
            "review_count": "⭐ Отзывов", "dimensions": "📐 Размеры",
            "box_capacity": "📦 Короб", "extra_services": "📸 Доп. услуги",
            "promo_code": "🏷️ Промокод",
        }
        for key, value in partial_fields.items():
            label = field_labels.get(key, key)
            msg += f"  {label}: {value}\n"

    if missing:
        msg += f"\n❌ Не заполнено: {', '.join(missing)}\n"

    msg += "\nБот попросил клиента заполнить форму повторно."

    try:
        await bot.send_message(
            config.manager_id,
            msg,
            reply_markup=get_manager_accept_kb(user.id)
        )
        logging.info(f"Manager notified about incomplete form from user {user.id}")
    except Exception as e:
        logging.error(f"Failed to notify manager about incomplete form: {e}")


async def notify_manager_lead(bot: Bot, user, lead_data: dict, raw_text: str = ""):
    """Notify manager: new lead, prepare PDF, connect to chat."""
    msg = (
        f"🆕 НОВАЯ ЗАЯВКА\n\n"
        f"👤 Клиент: {user.full_name}\n"
        f"📱 Telegram: @{user.username or 'нет username'}\n"
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

    has_fields = False
    for key, label in field_labels.items():
        value = lead_data.get(key)
        if value:
            msg += f"{label}: {value}\n"
            has_fields = True

    if not has_fields and raw_text:
        msg += f"\nСообщение клиента:\n{raw_text[:500]}\n"

    msg += "\n📋 Подготовьте PDF-расчёт и подключитесь к чату клиента."

    try:
        await bot.send_message(
            config.manager_id,
            msg,
            reply_markup=get_manager_accept_kb(user.id)
        )
        logging.info(f"Manager notified about lead from user {user.id}")
    except Exception as e:
        logging.error(f"Failed to notify manager: {e}")
