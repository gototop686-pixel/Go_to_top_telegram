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
from database.crud import save_user, update_user_language, log_interaction, save_chat_request, get_user as get_user_data
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
        f"\U0001f195 \u041f\u043e\u043b\u044c\u0437\u043e\u0432\u0430\u0442\u0435\u043b\u044c \u0437\u0430\u0448\u0435\u043b \u0432 \u0431\u043e\u0442\u0430!\n\n"
        f"\u0418\u043c\u044f: {user.full_name}\n"
        f"Username: @{user.username or 'N/A'}\n"
        f"ID: {user.id}"
    )
    try:
        await message.bot.send_message(config.manager_id, manager_msg, parse_mode=None)
    except Exception as e:
        logging.error(f"Failed to notify manager: {e}")
        
    await log_interaction(user.id, 'command', 'start', '/start', 'Welcome message')


@router.message(F.text == "\U0001f1f7\U0001f1fa \u0420\u0443\u0441\u0441\u043a\u0438\u0439")
@router.message(F.text == "\U0001f1e6\U0001f1f2 \u0540\u0561\u0575\u0565\u0580\u0565\u0576")
async def set_language(message: Message, state: FSMContext):
    lang = "ru" if "\u0420\u0443\u0441\u0441\u043a\u0438\u0439" in message.text else "am"
    await state.update_data(language=lang)
    
    # Persist to database
    await update_user_language(message.from_user.id, lang)
    
    i18n = lambda key: i18n_manager.get(key, lang)
    
    await message.answer(i18n("lang_selected"), reply_markup=get_main_menu_kb(i18n), parse_mode=None)


# ============================================================
# CHANGE LANGUAGE button (from main menu)
# ============================================================

@router.message(F.text.in_([
    i18n_manager.get("btn_change_language", "ru"),
    i18n_manager.get("btn_change_language", "am")
]))
async def change_language(message: Message, state: FSMContext):
    await message.answer(
        "\U0001f310 \u0412\u044b\u0431\u0435\u0440\u0438\u0442\u0435 \u044f\u0437\u044b\u043a / \u0538\u0576\u057f\u0580\u0565\u0584 \u056c\u0565\u0566\u0578\u0582\u0568:",
        reply_markup=get_language_kb(),
        parse_mode=None
    )


# show_price_list was moved to handlers/prices.py


# ============================================================
# HOW TO ORDER button
# ============================================================

@router.message(F.text.in_([
    i18n_manager.get("btn_how_to_order", "ru"),
    i18n_manager.get("btn_how_to_order", "am")
]))
async def show_how_to_order(message: Message, i18n):
    await message.answer(i18n("how_to_order_msg"), reply_markup=get_main_menu_kb(i18n), parse_mode=None)


# ============================================================
# ABOUT US button — with logo + HTML links
# ============================================================

@router.message(F.text.in_([
    i18n_manager.get("btn_about_us", "ru"),
    i18n_manager.get("btn_about_us", "am")
]))
async def show_about_us(message: Message, i18n):
    import os
    from aiogram.types import FSInputFile

    import html as html_lib
    about_text = html_lib.escape(i18n("about_us_msg"))
    links = i18n("about_us_links")  # Already HTML, don't escape
    
    # Build combined caption: escaped text + raw HTML links
    if links and links != "about_us_links":
        caption = f"{about_text}\n\n📱 {links}"
    else:
        caption = about_text

    # Send as ONE message: photo + caption
    logo_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets", "logo.jpg")
    if os.path.exists(logo_path):
        try:
            photo = FSInputFile(logo_path)
            # Telegram caption limit is 1024 chars
            if len(caption) <= 1024:
                await message.answer_photo(
                    photo,
                    caption=caption,
                    reply_markup=get_main_menu_kb(i18n),
                    parse_mode="HTML"
                )
            else:
                # Too long for caption — send photo then text
                await message.answer_photo(photo)
                await message.answer(caption, reply_markup=get_main_menu_kb(i18n), parse_mode="HTML")
            return
        except Exception as e:
            logging.error(f"Failed to send about us with photo: {e}")

    # Fallback: text only
    await message.answer(caption, reply_markup=get_main_menu_kb(i18n), parse_mode="HTML")


# ============================================================
# BACK TO MENU button
# ============================================================

@router.message(F.text.in_([
    i18n_manager.get("btn_back_to_menu", "ru"),
    i18n_manager.get("btn_back_to_menu", "am")
]))
async def back_to_menu(message: Message, i18n, state: FSMContext):
    await state.clear()
    await message.answer(i18n("main_menu"), reply_markup=get_main_menu_kb(i18n), parse_mode=None)


# ============================================================
# CONTACT MANAGER (from main menu)
# ============================================================

@router.message(F.text.in_([
    i18n_manager.get("btn_contact_manager", "ru"),
    i18n_manager.get("btn_contact_manager", "am")
]))
async def contact_manager_btn(message: Message, i18n, bot: Bot):
    await contact_manager(message, i18n, bot)


# MANAGER NOTIFICATION HELPERS
async def notify_manager_about_attempt(bot: Bot, user: types.User, context: str = None):
    """Notify the manager with context."""
    await save_chat_request(
        user_id=user.id,
        user_name=user.full_name or "",
        username=user.username or "",
        request_type="manager_request",
        message_preview=context or ""
    )

    tz = pytz.timezone('Asia/Yerevan')
    now = datetime.now(tz)
    current_hour = now.hour
    
    is_working = config.work_start_hour <= current_hour < config.work_end_hour
    prefix = "\u23f0 (\u0420\u0410\u0411\u041e\u0427\u0415\u0415 \u0412\u0420\u0415\u041c\u042f)" if is_working else "\U0001f319 (\u0412\u041d\u0415\u0420\u0410\u0411\u041e\u0427\u0415\u0415 \u0412\u0420\u0415\u041c\u042f)"
    
    # Get user language for flag
    _ud = await get_user_data(user.id)
    _ul = _ud.get("language", "ru") if _ud else "ru"
    _fl = "\U0001f1e6\U0001f1f2" if _ul == "am" else "\U0001f1f7\U0001f1fa"
    
    msg = (
        f"{prefix} {_fl} \U0001f64b \u041a\u043b\u0438\u0435\u043d\u0442 \u043f\u0440\u043e\u0441\u0438\u0442 \u0441\u0432\u044f\u0437\u0430\u0442\u044c\u0441\u044f!\n\n"
        f"\u0418\u043c\u044f: {user.full_name}\n"
        f"Username: @{user.username or 'N/A'}\n"
        f"ID: {user.id}\n"
    )
    if context:
        msg += f"\n\U0001f4dd \u041a\u043e\u043d\u0442\u0435\u043a\u0441\u0442:\n{context}"
    
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
