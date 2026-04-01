from aiogram import Router, F, Bot
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from states.user_states import SalesFunnel
from database.crud import update_user_data, log_interaction
from keyboards.reply import get_main_menu_kb, get_back_kb
from config.config import config

router = Router()

@router.message(F.text == F.apply(lambda text, i18n: i18n("btn_new_client")))
async def start_funnel(message: Message, i18n, state: FSMContext):
    await state.set_state(SalesFunnel.waiting_for_name)
    await message.answer(i18n("ask_name"), reply_markup=get_back_kb(i18n))

@router.message(SalesFunnel.waiting_for_name)
async def process_name(message: Message, i18n, state: FSMContext):
    if message.text.startswith("🔙") or message.text.lower() == "назад":
        await state.clear()
        await message.answer(i18n("main_menu"), reply_markup=get_main_menu_kb(i18n))
        return

    await state.update_data(name=message.text)
    await state.set_state(SalesFunnel.waiting_for_article)
    await message.answer(i18n("ask_article"))

@router.message(SalesFunnel.waiting_for_article)
async def process_article(message: Message, i18n, state: FSMContext):
    await state.update_data(article=message.text)
    await state.set_state(SalesFunnel.waiting_for_box_qty)
    await message.answer(i18n("ask_box_qty"))

@router.message(SalesFunnel.waiting_for_box_qty)
async def process_box_qty(message: Message, i18n, state: FSMContext):
    try:
        qty = int(message.text)
        await state.update_data(box_qty=qty)
        await state.set_state(SalesFunnel.waiting_for_planned_qty)
        await message.answer(i18n("ask_planned_qty"))
    except ValueError:
        await message.answer(i18n("invalid_input"))

@router.message(SalesFunnel.waiting_for_planned_qty)
async def process_planned_qty(message: Message, i18n, state: FSMContext, bot: Bot):
    try:
        qty = int(message.text)
        data = await state.get_data()
        data['planned_qty'] = qty
        
        # Save to DB
        await update_user_data(message.from_user.id, data)
        await log_interaction(message.from_user.id, 'funnel', 'complete', message.text, i18n("calculation_started"))

        # Notify user
        await message.answer(i18n("calculation_started"), reply_markup=get_main_menu_kb(i18n))

        # Handoff to manager
        manager_msg = i18n("manager_notification", 
                           name=data['name'], 
                           article=data['article'], 
                           box_qty=data['box_qty'], 
                           planned_qty=data['planned_qty'],
                           username=message.from_user.username or "N/A",
                           user_id=message.from_user.id)
        
        try:
            await bot.send_message(config.manager_id, manager_msg)
        except Exception as e:
            print(f"Failed to notify manager: {e}")

        await state.clear()
        
    except ValueError:
        await message.answer(i18n("invalid_input"))
