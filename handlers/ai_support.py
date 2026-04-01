from aiogram import Router, F
from aiogram.types import Message
from aiogram.fsm.context import FSMContext

from states.user_states import SupportMode, SalesFunnel
from services.ai_service import ai_service
from database.crud import log_interaction
from keyboards.reply import get_main_menu_kb, get_back_kb, get_yes_no_kb

from middlewares.i18n import i18n_manager

router = Router()

@router.message(F.text.in_([i18n_manager.get("btn_ask_question", "ru"), i18n_manager.get("btn_ask_question", "am")]))
async def start_questioning(message: Message, i18n, state: FSMContext):
    await state.set_state(SupportMode.asking_question)
    await message.answer(i18n("ask_question_prompt"), reply_markup=get_back_kb(i18n))

@router.message(SupportMode.asking_question)
async def process_question(message: Message, i18n, language: str, state: FSMContext):
    if message.text.startswith("🔙") or message.text.lower() == "назад":
        await state.clear()
        await message.answer(i18n("main_menu"), reply_markup=get_main_menu_kb(i18n))
        return

    # Trigger AI Mode
    answer = await ai_service.get_answer(message.text, language)
    
    # Log interaction
    await log_interaction(message.from_user.id, 'ai', 'questioning', message.text, answer)

    # Answer + CTA (already in AI answer or appended here)
    await message.answer(answer)
    
    # Soft CTA: ask user if they want a calculation
    await message.answer(i18n("fallback_question"), reply_markup=get_yes_no_kb(i18n))
    await state.clear()

@router.message(F.text.in_([i18n_manager.get("btn_yes_calculation", "ru"), i18n_manager.get("btn_yes_calculation", "am")]))
async def yes_to_calculation(message: Message, i18n, state: FSMContext):
    from handlers.sales_funnel import start_funnel
    await start_funnel(message, i18n, state)
