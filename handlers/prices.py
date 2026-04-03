from aiogram import Router, F
from aiogram.types import Message
from middlewares.i18n import i18n_manager
from keyboards.reply import get_main_menu_kb, get_price_categories_kb

router = Router()

# ============================================================
# PRICE LIST CATEGORIES (SUB-MENU)
# ============================================================

@router.message(F.text.in_([
    i18n_manager.get("btn_price_list", "ru"),
    i18n_manager.get("btn_price_list", "am")
]))
async def show_price_categories(message: Message, i18n):
    """Shows the 5 pricing categories as a sub-menu sub-keyboard."""
    await message.answer(
        i18n("price_categories_msg"), 
        reply_markup=get_price_categories_kb(i18n), 
        parse_mode="Markdown"
    )

# ============================================================
# INDIVIDUAL PRICE LISTS
# ============================================================

@router.message(F.text.in_([
    i18n_manager.get("btn_price_main", "ru"),
    i18n_manager.get("btn_price_main", "am")
]))
async def show_main_prices(message: Message, i18n):
    await message.answer(i18n("price_main_msg"), parse_mode="Markdown")

@router.message(F.text.in_([
    i18n_manager.get("btn_price_reviews", "ru"),
    i18n_manager.get("btn_price_reviews", "am")
]))
async def show_review_prices(message: Message, i18n):
    await message.answer(i18n("price_reviews_msg"), parse_mode="Markdown")

@router.message(F.text.in_([
    i18n_manager.get("btn_price_photo_video", "ru"),
    i18n_manager.get("btn_price_photo_video", "am")
]))
async def show_photo_video_prices(message: Message, i18n):
    await message.answer(i18n("price_photo_video_msg"), parse_mode="Markdown")

@router.message(F.text.in_([
    i18n_manager.get("btn_price_fulfillment", "ru"),
    i18n_manager.get("btn_price_fulfillment", "am")
]))
async def show_fulfillment_prices(message: Message, i18n):
    await message.answer(i18n("price_fulfillment_msg"), parse_mode="Markdown")

@router.message(F.text.in_([
    i18n_manager.get("btn_price_delivery", "ru"),
    i18n_manager.get("btn_price_delivery", "am")
]))
async def show_delivery_prices(message: Message, i18n):
    await message.answer(i18n("price_delivery_msg"), parse_mode="Markdown")
